# Story: Submit Lambda Handler (batch upload)

# Summary
As an application developer,
I want the Submit handler to mint one ticket and return presigned upload URLs for
a *batch* of PDFs,
so that a user can select several spending-statement PDFs at once and upload them
directly to S3 under a single ticket.

This revises the earlier single-file submit story. Submit now accepts and returns
a **batch** (many files, one ticket, one prefix), and it deliberately does **not**
start the pipeline. Starting the pipeline once all uploads land is the job of the
UploadWatcher Lambda (separate story: `Story 1 UploadWatcher.md`).

# Background
Submit (the path is `POST /spending-history`) is the unauthenticated front door
where session identity is created. It depends on the pure `mint_ticket` function
and must not reimplement minting.

Presigned URLs are per-object: one URL authorizes a PUT to exactly one key. A
batch of N PDFs therefore means N presigned URLs and N direct browser PUTs to S3.
The heavy bytes never pass through this Lambda or API Gateway.

Downstream architecture:
- S3 key structure: one ticket -> one prefix `uploads/<ticketId>/` -> many PDFs.
- The UploadWatcher monitors `uploads/<ticketId>/` and triggers Step Functions with
  `input-s3-uri: s3://<bucket>/uploads/<ticketId>` once all expected files land.
- *Downstream Compatibility Note:* Existing Normalizer implementations may expect
  numeric ticket paths (`s3://<bucket>/<numeric-ticket>/uploads`). Normalizer will
  be updated in a separate story to accept ULID ticket IDs under the `uploads/<ticketId>` prefix.

# Handler (mint + presign batch)

## Lambda Configuration & Environment Variables

| Parameter | Value | Notes |
|---|---|---|
| **Runtime** | `python3.12` | Python 3.12 |
| **Architecture** | `arm64` | AWS Graviton2 / Linux |
| **Handler** | `submit.lambda_handler.handler` | Module entrypoint |
| **Memory** | `256 MB` | Lightweight orchestration only |
| **Timeout** | `15 seconds` | Quick turnaround for API Gateway |
| **Ephemeral Storage (/tmp)** | `512 MB` | Default (no local file downloads) |

### Environment Variables
- `TICKETS_TABLE_NAME` *(required, string)*: DynamoDB table name for tickets (e.g. `pii-tickets-dev`).
- `UPLOADS_BUCKET_NAME` *(required, string)*: Target S3 bucket for uploads.
- `MAX_FILES` *(optional, integer, default: 20)*: Maximum allowed files per batch.
- `MAX_TOTAL_BYTES` *(optional, integer, default: 4294967296 / 4 GiB)*: Maximum cumulative batch size.
- `PRESIGNED_EXPIRY_SECONDS` *(optional, integer, default: 900)*: Presigned PUT URL expiration in seconds.
- `TICKET_TTL_SECONDS` *(optional, integer, default: 86400)*: Ticket TTL in seconds passed to `mint_ticket`.

## Event Contract (API Gateway Proxy & Direct Invocation)

The handler supports API Gateway Lambda Proxy integration (HTTP API v2 or REST API)
where the request payload is passed in `event["body"]` (as a JSON string, handling
`isBase64Encoded` if needed), as well as direct invocation where `event` is the payload dictionary.

Request Body JSON:
```json
{
  "files": [
    { "filename": "jan.pdf", "fileSizeBytes": 5242880 },
    { "filename": "feb.pdf", "fileSizeBytes": 3145728 }
  ]
}
```

Validation rules:
- `files`: required, non-empty array of file descriptor objects.
- Per file:
  - `filename`: required string, basename only (reject `/`, `\`, `..`), must end in `.pdf` (case-insensitive), must contain non-whitespace characters before `.pdf`, and should contain standard safe characters (alphanumerics, dots, dashes, underscores).
  - `fileSizeBytes`: required integer, between 1 MB (1,048,576 bytes) and 15 MB (15,728,640 bytes) each.
- **Batch limits:**
  - Reject with 400 if file count exceeds `MAX_FILES` (default 20).
  - Reject with 400 if summed `fileSizeBytes` exceeds `MAX_TOTAL_BYTES` (default 4 GiB).
- **Filename collisions:**
  - Reject with 400 if the batch contains duplicate filenames (evaluated case-insensitively). The error response must identify which filename collided.

## Output Contract (API Gateway Proxy Response)

The handler returns an API Gateway proxy response with CORS headers enabled:
```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS"
  },
  "body": "{\"ticketId\": \"01ARZ3NDEKTSV4RRFFQ69G5FAV\", ...}"
}
```

Response Body JSON (deserialized `body`):
```json
{
  "ticketId": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "secret": "<base64url secret, returned once>",
  "uploadPrefix": "uploads/01ARZ3NDEKTSV4RRFFQ69G5FAV/",
  "uploads": [
    {
      "filename": "jan.pdf",
      "key": "uploads/01ARZ3NDEKTSV4RRFFQ69G5FAV/jan.pdf",
      "uploadUrl": "<presigned PUT URL>"
    },
    {
      "filename": "feb.pdf",
      "key": "uploads/01ARZ3NDEKTSV4RRFFQ69G5FAV/feb.pdf",
      "uploadUrl": "<presigned PUT URL>"
    }
  ],
  "expectedFileCount": 2,
  "expiresInSeconds": 900
}
```

### Presigned URL Specifications
- Method: S3 `put_object`.
- Parameters pinned in signature:
  - `Bucket`: `UPLOADS_BUCKET_NAME`
  - `Key`: `uploads/<ticketId>/<filename>`
  - `ContentType`: `"application/pdf"` (client must send `Content-Type: application/pdf` during HTTP PUT).
- Expiration: `PRESIGNED_EXPIRY_SECONDS` (default: 900).

## DynamoDB Integration & Handler Flow

1. **Parse & Validate:**
   - Extract JSON from `event["body"]` (or direct `event`).
   - Validate batch constraints and filenames. On validation error, immediately return 400 proxy response without calling DynamoDB or S3.
2. **Mint Ticket:**
   - Call `mint_ticket(table_name=TICKETS_TABLE_NAME, ttl_seconds=TICKET_TTL_SECONDS, dynamodb_client=...)`.
   - Returns `{ "ticket_id": "<ULID>", "secret": "<raw_secret>" }`.
   - The initial row is created by `mint_ticket` with `job_status: "issued"`.
3. **Follow-up UpdateItem:**
   - Execute a follow-up `dynamodb_client.update_item(...)` to set the upload expectations:
     - `TableName`: `TICKETS_TABLE_NAME`
     - `Key`: `{"ticket_id": {"S": ticket_id}}`
     - `UpdateExpression`: `"SET #status = :new_status, #count = :count"`
     - `ExpressionAttributeNames`: `{"#status": "job_status", "#count": "expected_file_count"}`
     - `ExpressionAttributeValues`: `{":new_status": {"S": "AWAITING_UPLOAD"}, ":count": {"N": str(len(files))}}`
     - `ConditionExpression`: `"attribute_exists(ticket_id)"`
   - *Note:* Attribute `expected_file_count` is stored in snake_case, consistent with `ticket_id`, `secret_hash`, and `job_status`.
4. **Generate Presigned URLs:**
   - For each file, construct key `uploads/<ticketId>/<filename>` and call `s3_client.generate_presigned_url('put_object', Params={'Bucket': bucket, 'Key': key, 'ContentType': 'application/pdf'}, ExpiresIn=expires_in)`.
5. **Format & Return Response:**
   - Return 200 proxy response with CORS headers and response body.
   - **Do NOT StartExecution here.** Pipeline initiation is exclusively owned by UploadWatcher.

Module: `backend/submit/src/submit/lambda_handler.py`
Entry: `submit.lambda_handler.handler`
Clients injectable via module-level factory or parameters for testing.

# Client responsibilities (informative)
- Read `uploads` array from the 200 response and perform direct HTTP PUT to each `uploadUrl`.
- The client MUST include header `Content-Type: application/pdf` in each PUT request to match the presigned URL signature.
- Fire the N PUTs in parallel; retry individually per-file on network/S3 errors.
- Successful PUTs emit `s3:ObjectCreated` events that trigger UploadWatcher. No explicit client "I'm done" call is needed.

# Error handling
- **Validation errors (400):** Malformed JSON, missing `files`, invalid filenames, duplicate filenames, file size < 1 MB or > 15 MB, file count > `MAX_FILES`, total size > `MAX_TOTAL_BYTES`. Return structured JSON error body with `statusCode: 400` and CORS headers.
- **Downstream failures (500):** DynamoDB or S3 failures return `statusCode: 500`.
- **Security & Privacy:** The raw `secret` and presigned URLs must NEVER be logged or printed to CloudWatch. The `ticket_id` is public and safe to log for correlation.

# Out of scope
- Terraform for API Gateway route, IAM roles, DynamoDB table, S3 bucket.
- The frontend UI / browser upload implementation and client-side retry logic.
- `mint_ticket` internals (the issuer module is consumed as a dependency).
- Starting Step Functions execution (owned by UploadWatcher).
- Upload timeout sweeper / cleanup for abandoned uploads.

# Packaging
- ZIP deployment package with dependencies (no container).
- Python 3.12, arm64, uv for dependency management.
- Build script `backend/submit/build_n_package_lambda.sh`, mirroring `backend/pdf2csv/build_n_package_lambda.sh`:
  1. Clean/create the `build_lambda` directory.
  2. In a `public.ecr.aws/lambda/python:3.12` Docker container (`--platform linux/arm64`), install uv and run:
     `uv pip install . --target build_lambda`.
  3. Remove tests and `__pycache__`; strip `.so` files.
  4. Zip to `submit.zip`; print package name, SHA-256 digest, handler (`submit.lambda_handler.handler`), runtime, and target.

# Documentation
Add `backend/submit/submit_deployment.md`, mirroring the structure of `backend/pdf2csv/Normalizer_deployment.md`:
- Overview
- Lambda Deployment: Prerequisites (Docker, Python 3.12, uv, zip), Building the Package (`build_n_package_lambda.sh`), Lambda Configuration (arm64, Python 3.12, handler `submit.lambda_handler.handler`, 256 MB, 15 s timeout, 512 MB ephemeral storage), Environment Variables table, Event Contract (API Gateway proxy payload), Lambda Success Response with CORS headers, Direct Lambda Testing (local Python invocation + `aws lambda invoke` examples).
- Testing methodology: Unit tests, local invocation, AWS CLI invocation.
- Pipeline Coordination: Brief note explaining the role of Submit vs UploadWatcher, confirming Submit does NOT trigger Step Functions.

# Acceptance criteria
- A valid batch returns HTTP 200 with CORS headers, containing one `ticketId`, one `secret`, and an `uploads` array with one presigned PUT URL per file under `uploads/<ticketId>/`.
- Presigned PUT URLs enforce `ContentType: "application/pdf"`.
- `mint_ticket` is called exactly once per valid request; an immediate `update_item` records `expected_file_count` (snake_case) and transitions `job_status` to `AWAITING_UPLOAD`.
- Submit handler does NOT start any Step Functions execution.
- Invalid requests (duplicate filenames, size out of bounds, missing fields, count > `MAX_FILES`) return HTTP 400 with a descriptive error message and no ticket is minted.
- Raw secret and presigned URLs never appear in logs.
- Handler accepts both API Gateway proxy events (`event["body"]`) and direct payload dictionaries.
- AWS clients (`boto3` DynamoDB and S3) are injectable for unit testing without live AWS access.
- Packaging script `build_n_package_lambda.sh` produces a reproducible arm64 ZIP package for Python 3.12 using uv.
- `submit_deployment.md` accurately documents 256 MB / 15 s configuration, required environment variables, event/response contracts with CORS, and direct invocation examples.
- Unit tests achieve at least 80% coverage covering validation, happy path orchestration, DynamoDB failure, and S3 presign handling.

# Open item flagged
- Count-based completion (enforced by UploadWatcher) assumes the user uploads exactly the declared set of files. If a file's PUT never succeeds or is abandoned, the ticket remains in `AWAITING_UPLOAD`. Mitigations for a later story: a client finalize endpoint or a scheduled sweeper Lambda that expires stuck tickets.
