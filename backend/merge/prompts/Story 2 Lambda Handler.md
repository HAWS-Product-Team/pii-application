# Story: Create Merge Lambda for Staged Pipeline

# Summary

As an application developer,
I want the merge program to run as an AWS Lambda function,
so that it can execute after pdf2csv (Normalizer) has produced the csv files.  
This is done with lambda so as to not require a heavyweight, slower-starting container.

# Background
The python application is called `merge` and will have the same name at the stepfunction level and lambda level.
Merge will run after Normalizer in the pipeline (AWS state machine).

The pipeline has a staged architecture:
Normalizer -> Merge -> Classifier -> PIICalculation
- Normalizer: AWS Lambda (ZIP package, Python 3.12, arm64). Converts user-uploaded spending-statement PDFs to CSVs in place in S3.
- Merge: AWS Lambda combines the csv files into a single csv file.
- Classifier: already containerized, runs on AWS Batch (the expensive inference workload).
- PIICalculation: short-running (seconds); runs as Lambda (see backend/PIICalculator/pii-calculator_deployment.md).

The merge Python application already implements the merging functionality (CLI: merge <input directory> <output file>). 
This story adds a Lambda orchestration layer on top of it. The conversion logic is already implemented and tested and 
is out of scope for changes. The app's CLI accepts local paths and s3://.

The Lambda is invoked by Step Functions with an event detailing the S3 location of the CSV files produced by Normalizer (pdf2csv). 
Inputs are the normalized CSV files generated from raw user-uploaded PDFs.

# Event Contract

```json
{
  "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload",
  "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/purchase_data.csv"
}
```
- input-s3-uri is required.
- output-s3-uri is required.
- Must be a well-formed s3://bucket/key URI (non-empty bucket and key).
- Trailing slash is optional; normalize before use.
- The first path segment after the bucket is the ticket number; it must be present and numeric.
- Extra event fields are ignored; the ticket is always derived from the path.

# Output Contract

- A CSV file is written to a S3 location.
- Existing objects at the output key are overwritten (idempotent re-runs).
- The output CSV contains the columns required by PIICalculation: date,item_description,quantity,unit_price,total_price (guaranteed by Normalizer).

# Handler

- Module: backend/merge/src/merge/lambda_handler.py
- Entry point: merge.lambda_handler.handler
- Runtime: Python 3.12, arm64
- Memory: 1536 MB
- Timeout: 180 seconds (3 min)
- Ephemeral storage (/tmp): 5 GB

# Handler Flow (Orchestration)

1. Validate the event (see Event Contract). On failure, raise MergeError.
2. List all objects under the input prefix (recursive). Select keys ending in .csv (case-insensitive); ignore other objects.
3. If no CSVs are found, raise MergeError ("no CSVs at input path").
4. Sum the sizes of the selected CSVs (from the list response — no extra API call). If the total exceeds the 
ephemeral-storage budget (default: 80% of the 5 GB /tmp), raise MergeError ("input too large for ephemeral storage").
5. Download the CSVs to a temporary input directory under /tmp.
6. Invoke the existing merge app's conversion over the temporary directory — local paths only. 
Prefer the app's Python API; fall back to the CLI merge <read_dir> <write_filename>. 
The app writes one merged CSV for all the input CSVs into a temporary output path.
7. Upload the produced CSV to S3 at the destination key (output-s3-uri). 
Verify a CSV was produced; if not, raise MergeError.
8. Clean up temporary directories always, including on failure.
9. Return the success response.

The S3 client must be created via a module-level factory (or otherwise injectable) so unit tests can fake it.

# Error Handling

- All failures raise MergeError with a clear, actionable message. No structured error payload — 
the unhandled exception causes Step Functions to mark the Merge state failed.
- Distinct error cases:
  - missing input-s3-uri
  - missing output-s3-uri
  - malformed S3 URI
  - missing/invalid (non-numeric) ticket number
  - no CSVs at the input path
  - total input size exceeds the ephemeral-storage budget
  - S3 read failure (access denied, invalid credentials, object not found)
  - conversion failure (unreadable/invalid CSV, app error)
  - S3 write failure
- Error messages include the ticket number and the offending S3 key where applicable.
- Never log CSV contents — log only the ticket, file names, counts, and S3 keys. Never write CSV data to stdout.

Success Response
────────────────────────

```json
{
  "ticket": "123456789",
  "status": "SUCCEEDED",
  "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/purchase_data.csv"
}
```
Exactly these three fields.

Compatibility with Existing CLI
───────────────────────────────────────

- The existing CLI (merge path/to/read_from filename/to/write_to) remains available for local development and is unchanged.
- The Lambda handler reuses the app's conversion.

Packaging
──────────────

- ZIP deployment package with dependencies (no container).
- Python 3.12, arm64, uv for dependency management.
- Build script backend/merge/build_n_package_lambda.sh, mirroring backend/pdf2csv/build_n_package_lambda.sh:
  1. Clean/create the build_lambda directory.
  2. In a public.ecr.aws/lambda/python:3.12 Docker container (--platform linux/arm64), 
  install uv and run uv pip install . --target build_lambda.
  3. Remove tests and __pycache__; strip .so files.
  4. Zip to merge.zip; print package name, SHA-256 digest, handler (merge.lambda_handler.handler), 
  runtime, and target.

Documentation
────────────────────

Add backend/merge/merge_deployment.md, mirroring the structure of backend/pdf2csv/Normalizer_deployment.md:
- Overview
- Lambda Deployment: Prerequisites (Docker, Python 3.12, uv, zip), Building the Package, Lambda Configuration 
(arm64, Python 3.12, handler, 1536 MB, 180 s, 5 GB ephemeral storage; no environment variables currently required), 
Event Contract, Lambda Success Response, Direct Lambda Testing (local Python snippet + aws lambda invoke example)
- Testing methodology 
- Step Functions: brief note that the state machine is owned by the infra repo; show the expected event shape and how 
to trigger once wired (per the terraform plan), mirroring the Normalizer doc

Testing
────────────

- Unit tests: pytest (existing tests/ layout). S3 is faked with pytest-mock (boto3 client) and the app's conversion is 
mocked — the conversion logic is already tested elsewhere; these tests cover orchestration only.
- Cases:
  1. Valid event → success response with correct ticket, status, output-s3-uri.
  2. Event missing input-s3-uri → MergeError. 
  3. Event missing output-s3-uri → MergeError.
  4. Malformed S3 URIs (http://..., s3://, s3://bucket) → MergeError.
  5. Missing/invalid ticket (s3://bucket/, s3://bucket/upload) → MergeError.
  6. Trailing-slash URI accepted and handled identically.
  7. CSVs are listed and downloaded from S3; conversion invoked over the directory.
  8. Output CSV uploaded to the correct key (output-s3-uri).
  9. No CSVs at the prefix → MergeError.
  10. Total input size exceeds the /tmp budget → MergeError (raised before any download).
  11. S3 read failure → MergeError.
  12. S3 write failure → MergeError.
  13. Merge produces no CSV for input CSVs → MergeError.
  14. No CSV contents appear in logs or stdout.
- Existing merge CLI tests continue to pass.
- No real AWS calls in unit tests.

Manual Validation
───────────────────────

A developer can run the handler locally with a representative event:
```json
{
  "input-s3-uri": "s3://pii-data-pipeline-input/1234/uploads",
  "output-s3-uri": "s3://pii-data-pipeline-input/1234/purchase_data.csv"
}
```
- Against local filesystem
- Against real S3 with dev credentials (as in the PIICalculator doc's "Direct Lambda Testing").

Acceptance Criteria
──────────────────────────

- A Merge Lambda handler exists at backend/merge/src/merge/lambda_handler.py with entry point merge.lambda_handler.handler.
- The handler accepts input-s3-uri (trailing slash optional), output-s3-uri (to a filename so there will be no 
trailing slash), validates S3 URI format, and validates a numeric ticket number after the bucket name.
- The handler lists CSVs under the prefix and errors when none are found.
- The handler guards total input size against the /tmp budget and errors before downloading when exceeded.
- The handler downloads the CSVs, merges them, and uploads a single CSV (the merged file) named by the output-s3-uri.
- The handler returns a success response containing exactly ticket, status, output-s3-uri.
- The handler raises MergeError for invalid events, missing/unreadable CSVs, conversion failures, and write failures.
- The handler does not log raw CSV contents and does not write CSVs to stdout.
- The handler does not require running in a container.
- The Lambda package is a ZIP built for Python 3.12 / arm64 via build_n_package_lambda.sh using uv; production 
dependencies install reproducibly.
- merge_deployment.md documents configuration (1536 MB, 180 s, 5 GB ephemeral storage), event/response contracts, 
direct testing, and local filesystem validation.
- New unit tests cover the handler's orchestration behavior with S3 and conversion mocked; existing tests pass.

Out of Scope
─────────────────

- Changes to the existing merge logic (already implemented and tested).
- Step Functions infrastructure (owned by the infra repo, which consumes this package).
- Frontend integration.
- API changes for starting pipeline executions.
- IAM/infra provisioning.