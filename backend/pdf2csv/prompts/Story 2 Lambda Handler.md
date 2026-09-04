# Story: Create Normalizer Lambda for Staged Pipeline

# Summary

As an application developer,
I want the pdf2csv workload to run as an AWS Lambda function,
so that the lightweight pdf2csv stage can execute after the user has uploaded their spending-statement PDFs, 
without a heavyweight, slower-starting container.

# Background
Although the python application is called pdf2csv, at the stepfunction level and lamda level, let's call it Normalizer as this program 
will grow to handle other formats and everything must be normalize into csv.  
The Normalizer Lambda will be the first stage in the pipeline.

The pipeline has moved to a staged architecture:
Normalizer -> Classifier -> PIICalculation
- Normalizer (this story): AWS Lambda (ZIP package, Python 3.12, arm64). Converts user-uploaded spending-statement PDFs to CSVs in place in S3.
- Classifier: already containerized, runs on AWS Batch (the expensive inference workload).
- PIICalculation: short-running (seconds); runs as Lambda (see backend/PIICalculator/pii-calculator_deployment.md).

The pdf2csv Python application already implements the PDF→CSV conversion (pypdf-based; CLI: pdf2csv <read_dir> <write_dir>). 
This story adds a Lambda orchestration layer on top of it. The conversion logic is already implemented and tested and 
is out of scope for changes. The app's CLI accepts local paths only (no s3:// support); all S3 I/O is the Lambda handler's responsibility.

The Lambda is invoked by Step Functions with an event detailing the S3 location of the uploaded PDFs. 
Inputs are the raw user-uploaded PDFs (pdf2csv is the first stage).

# Event Contract

{ "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload" }
- input-s3-uri is required.
- Must be a well-formed s3://bucket/key URI (non-empty bucket and key).
- Trailing slash is optional; normalize before use.
- The first path segment after the bucket is the ticket number; it must be present and numeric.
- Extra event fields are ignored; the ticket is always derived from the path.

# Output Contract

- CSVs are written to the same S3 location as the input (same bucket, same prefix).
- Output key = input key with the extension replaced by .csv (e.g., 123456789/upload/statement.pdf → 123456789/upload/statement.csv).
- Existing objects at the output key are overwritten (idempotent re-runs).
- Output CSVs contain the columns required by PIICalculation: date,item_description,quantity,unit_price,total_price (guaranteed by the existing app).

# Handler

- Module: backend/pdf2csv/src/pdf2csv/lambda_handler.py
- Entry point: pdf2csv.lambda_handler.handler
- Runtime: Python 3.12, arm64
- Memory: 1536 MB
- Timeout: 180 seconds (3 min)
- Ephemeral storage (/tmp): 5 GB

# Handler Flow (Orchestration)

1. Validate the event (see Event Contract). On failure, raise Pdf2CsvError.
2. List all objects under the input prefix (recursive). Select keys ending in .pdf (case-insensitive); ignore other objects.
3. If no PDFs are found, raise Pdf2CsvError ("no PDFs at input path").
4. Sum the sizes of the selected PDFs (from the list response — no extra API call). If the total exceeds the 
ephemeral-storage budget (default: 80% of the 5 GB /tmp), raise Pdf2CsvError ("input too large for ephemeral storage").
5. Download the PDFs to a temporary input directory under /tmp.
6. Invoke the existing pdf2csv app's conversion over the temporary directory — local paths only 
(the CLI does not accept s3:// URIs). Prefer the app's Python API; fall back to the CLI pdf2csv <read_dir> <write_dir>. 
The app writes one CSV per PDF into a temporary output directory.
7. Upload each produced CSV to S3 at the corresponding key (same key, .csv extension). 
Verify a CSV was produced for every input PDF; if any are missing, raise Pdf2CsvError.
8. Clean up temporary directories always, including on failure.
9. Return the success response.

The S3 client must be created via a module-level factory (or otherwise injectable) so unit tests can fake it.

# Error Handling

- All failures raise Pdf2csvError with a clear, actionable message. No structured error payload — 
the unhandled exception causes Step Functions to mark the Normalizer state failed.
- Distinct error cases:
  - missing input-s3-uri
  - malformed S3 URI
  - missing/invalid (non-numeric) ticket number
  - no PDFs at the input path
  - total input size exceeds the ephemeral-storage budget
  - S3 read failure (access denied, invalid credentials, object not found)
  - conversion failure (unreadable/invalid PDF, app error)
  - S3 write failure
- Error messages include the ticket number and the offending S3 key where applicable.
- Never log PDF or CSV contents — log only the ticket, file names, counts, and S3 keys. Never write CSV data to stdout.

Success Response
────────────────────────

{ "ticket": "123456789", "status": "SUCCEEDED",
  "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload" }
Exactly these three fields. output-s3-uri is the input URI as provided in the event.

Compatibility with Existing CLI
───────────────────────────────────────

- The existing CLI (pdf2csv path/to/read_from path/to/write_to) remains available for local development and is unchanged.
- The Lambda handler reuses the app's conversion; for S3, input URI == output URI.

Packaging
──────────────

- ZIP deployment package with dependencies (no container).
- Python 3.12, arm64, uv for dependency management.
- Build script backend/pdf2csv/build_n_package_lambda.sh, mirroring backend/PIICalculator/build_n_package_lambda.sh:
  1. Clean/create the build_lambda directory.
  2. In a public.ecr.aws/lambda/python:3.12 Docker container (--platform linux/arm64), 
  install uv and run uv pip install . --target build_lambda.
  3. Remove tests and __pycache__; strip .so files.
  4. Zip to Normalizer-lambda.zip; print package name, SHA-256 digest, handler (Normalizer.lambda_handler.handler), 
  runtime, and target.

Documentation
────────────────────

Add backend/pdf2csv/Normalizer_deployment.md, mirroring the structure of backend/PIICalculator/pii-calculator_deployment.md:
- Overview
- Lambda Deployment: Prerequisites (Docker, Python 3.12, uv, zip), Building the Package, Lambda Configuration 
(arm64, Python 3.12, handler, 1536 MB, 180 s, 5 GB ephemeral storage; no environment variables currently required), 
Event Contract, Lambda Success Response, Direct Lambda Testing (local Python snippet + aws lambda invoke example)
- Local Validation with LocalStack: copy-pasteable steps — start LocalStack, create the bucket, upload a sample PDF, 
run the handler with a representative event (boto3 pointed at the LocalStack endpoint), verify the output CSV in S3
- Step Functions: brief note that the state machine is owned by the infra repo; show the expected event shape and how 
to trigger once wired (per the terraform plan), mirroring the PIICalculator doc

Testing
────────────

- Unit tests: pytest (existing tests/ layout). S3 is faked with pytest-mock (boto3 client) and the app's conversion is 
mocked — the conversion logic is already tested elsewhere; these tests cover orchestration only.
- Cases:
  1. Valid event → success response with correct ticket, status, output-s3-uri.
  2. Event missing input-s3-uri → Pdf2CsvError.
  3. Malformed S3 URIs (http://..., s3://, s3://bucket) → Pdf2CsvError.
  4. Missing/invalid ticket (s3://bucket/, s3://bucket/upload) → Pdf2CsvError.
  5. Trailing-slash URI accepted and handled identically.
  6. PDFs are listed and downloaded from S3; conversion invoked over the directory.
  7. CSVs uploaded to the correct keys (same key, .csv extension).
  8. No PDFs at the prefix → Pdf2CsvError.
  9. Total input size exceeds the /tmp budget → Pdf2CsvError (raised before any download).
  10. S3 read failure → Pdf2CsvError.
  11. S3 write failure → Pdf2CsvError.
  12. Conversion produces no CSV for an input PDF → Pdf2CsvError.
  13. No PDF/CSV contents appear in logs or stdout.
- Existing pdf2csv CLI tests continue to pass.
- No real AWS calls in unit tests.

Manual Validation
───────────────────────

A developer can run the handler locally with a representative event:
{ "input-s3-uri": "s3://pii-data-pipeline-input/1234/upload" }
- Against LocalStack (primary; per the deployment doc's LocalStack section).
- Against real S3 with dev credentials (as in the PIICalculator doc's "Direct Lambda Testing").

Acceptance Criteria
──────────────────────────

- A Normalizer Lambda handler exists at backend/pdf2csv/src/pdf2csv/lambda_handler.py with entry point pdf2csv.lambda_handler.handler.
- The handler accepts input-s3-uri (trailing slash optional), validates S3 URI format, and validates a numeric ticket 
number after the bucket name.
- The handler lists PDFs under the prefix and errors when none are found.
- The handler guards total input size against the /tmp budget and errors before downloading when exceeded.
- The handler downloads the PDFs, invokes the existing app's conversion, and uploads CSVs to the same 
location with .csv extensions.
- The handler returns a success response containing exactly ticket, status, output-s3-uri.
- The handler raises Pdf2CsvError for invalid events, missing/unreadable PDFs, conversion failures, and write failures.
- The handler does not log raw PDF/CSV contents and does not write CSVs to stdout.
- The handler does not require running in a container.
- The Lambda package is a ZIP built for Python 3.12 / arm64 via build_n_package_lambda.sh using uv; production 
dependencies install reproducibly.
- normalizer_deployment.md documents configuration (1536 MB, 180 s, 5 GB ephemeral storage), event/response contracts, 
direct testing, and LocalStack validation.
- New unit tests cover the handler's orchestration behavior with S3 and conversion mocked; existing tests pass.

Out of Scope
─────────────────

- Changes to the existing PDF→CSV conversion logic (already implemented and tested).
- Step Functions infrastructure (owned by the infra repo, which consumes this package).
- Frontend integration.
- API changes for starting pipeline executions.
- IAM/infra provisioning.
- The PIICalculator Lambda (already deployed; see its deployment doc).