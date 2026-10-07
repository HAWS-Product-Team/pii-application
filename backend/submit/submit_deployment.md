# Submit Lambda Deployment & Local Validation

## Overview

The **Submit** Lambda function is the entrypoint ("front door") for the PII Data Pipeline:

```
Client (Browser / CLI) ──► Submit (Lambda) ──► Direct S3 Upload (Presigned PUTs) ──► UploadWatcher (Lambda) ──► Step Functions Pipeline
```

Submit handles unauthenticated requests to `POST /spending-history`. It receives a batch descriptor of PDF statements to be uploaded, validates the batch against file count and size limits, mints a session credential (`ticket_id` ULID and `secret` bearer token) via `mint_ticket`, records the expected file count and `AWAITING_UPLOAD` status in DynamoDB, and generates individual presigned S3 PUT URLs for each file under `uploads/<ticketId>/`.

Large file payloads never pass through API Gateway or this Lambda; the browser PUTs files directly to S3.

---

## Lambda Deployment

### Prerequisites

- **Docker**: For reproducible arm64 Linux builds via official AWS Lambda base images
- **Python 3.12**: Runtime version
- **uv**: Fast Python packaging and dependency resolver
- **zip**: Packaging utility

### Building the Package

Run the packaging script from `backend/submit`:

```bash
chmod +x build_n_package_lambda.sh
./build_n_package_lambda.sh
```

This script:
1. Cleans the `build_lambda/` staging directory.
2. Runs a `public.ecr.aws/lambda/python:3.12` Docker container under `--platform linux/arm64`.
3. Installs dependencies using `uv pip install --system --target build_lambda .`.
4. Removes unnecessary build artifacts (`tests/`, `__pycache__`, `.pyc`, etc.) and strips `.so` binaries.
5. Archives the build directory into `submit.zip` and outputs the package SHA-256 digest.

### Lambda Configuration

| Parameter | Value | Notes |
|---|---|---|
| **Runtime** | `python3.12` | Python 3.12 |
| **Architecture** | `arm64` | AWS Graviton2 / Linux |
| **Handler** | `submit.lambda_handler.handler` | Module entrypoint |
| **Memory** | `256 MB` | Lightweight orchestration only |
| **Timeout** | `15 seconds` | Quick turnaround for API Gateway |
| **Ephemeral Storage (/tmp)** | `512 MB` | Default (no local file downloads) |

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TICKETS_TABLE_NAME` | Yes | - | DynamoDB table name for tickets (e.g. `pii-tickets-dev`) |
| `UPLOADS_BUCKET_NAME` | Yes | - | S3 bucket receiving uploaded PDFs (e.g. `pii-data-pipeline-input-dev`) |
| `MAX_FILES` | No | `20` | Maximum number of files permitted per batch |
| `MAX_TOTAL_BYTES` | No | `4294967296` (4 GiB) | Maximum cumulative batch size |
| `PRESIGNED_EXPIRY_SECONDS` | No | `900` (15 min) | Presigned PUT URL expiration in seconds |
| `TICKET_TTL_SECONDS` | No | `86400` (24 hr) | Ticket credential TTL in seconds passed to `mint_ticket` |

### Event Contract

The handler supports API Gateway Lambda Proxy integration (HTTP API v2 or REST API) where the payload is passed in `event["body"]`, as well as direct invocation where `event` is the payload dictionary:

```json
{
  "files": [
    { "filename": "january_statement.pdf", "fileSizeBytes": 5242880 },
    { "filename": "february_statement.pdf", "fileSizeBytes": 3145728 }
  ]
}
```

Validation rules:
- `files`: required, non-empty list of file descriptor objects.
- `filename`: required string, basename only (no `/`, `\`, or `..`), must end with `.pdf` (case-insensitive), must contain characters before extension, and alphanumeric/safe characters only (`[a-zA-Z0-9._-]`).
- `fileSizeBytes`: required integer between 1 MB (1,048,576 bytes) and 15 MB (15,728,640 bytes) each.
- Batch limits: count must not exceed `MAX_FILES` (default 20); summed size must not exceed `MAX_TOTAL_BYTES` (default 4 GiB).
- Duplicate filenames: duplicate names (evaluated case-insensitively) are rejected with HTTP 400.

### Lambda Success Response

Returns standard API Gateway proxy response with CORS headers:

```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS"
  },
  "body": "{\"ticketId\": \"01K0A1B2C3D4E5F6G7H8J9K0L1\", \"secret\": \"...\", ...}"
}
```

Deserialized `body` content:

```json
{
  "ticketId": "01K0A1B2C3D4E5F6G7H8J9K0L1",
  "secret": "s-c4q7W9r_...",
  "uploadPrefix": "uploads/01K0A1B2C3D4E5F6G7H8J9K0L1/",
  "uploads": [
    {
      "filename": "january_statement.pdf",
      "key": "uploads/01K0A1B2C3D4E5F6G7H8J9K0L1/january_statement.pdf",
      "uploadUrl": "https://pii-data-pipeline-input-dev.s3.amazonaws.com/uploads/01K0A1B2C3D4E5F6G7H8J9K0L1/january_statement.pdf?..."
    },
    {
      "filename": "february_statement.pdf",
      "key": "uploads/01K0A1B2C3D4E5F6G7H8J9K0L1/february_statement.pdf",
      "uploadUrl": "https://pii-data-pipeline-input-dev.s3.amazonaws.com/uploads/01K0A1B2C3D4E5F6G7H8J9K0L1/february_statement.pdf?..."
    }
  ],
  "expectedFileCount": 2,
  "expiresInSeconds": 900
}
```

---

## Testing

Testing follows a layered progression from unit tests to local invocation and deployed Lambda validation:

- **Unit tests**: Fast automated validation of handler logic and CLI with mocked AWS dependencies (`pytest`).
- **Local invocation**: Running the handler or CLI locally against real or LocalStack AWS resources.
- **Deployed Lambda invocation**: Testing the function in AWS via API Gateway or AWS CLI.

### 1. Unit Tests

Run tests and check coverage using `uv`:

```bash
cd backend/submit
uv run pytest --cov=submit --cov-report=term-missing
```

### 2. Direct Lambda Testing (Local Python Invocation)

```python
import json
import os
from submit.lambda_handler import handler

os.environ["TICKETS_TABLE_NAME"] = "pii-tickets-dev"
os.environ["UPLOADS_BUCKET_NAME"] = "pii-data-pipeline-input-dev"

event = {
    "body": json.dumps({
        "files": [
            {"filename": "statement1.pdf", "fileSizeBytes": 2097152},
            {"filename": "statement2.pdf", "fileSizeBytes": 3145728}
        ]
    })
}

response = handler(event)
print("Status Code:", response["statusCode"])
print("Body:", response["body"])
```

### 3. AWS CLI Invocation

Deploy `submit.zip` via Terraform or copy directly to S3 deployment bucket.
To invoke the deployed Lambda directly via AWS CLI:

```bash
aws lambda invoke \
  --function-name pii-submit-dev \
  --payload '{"body": "{\"files\": [{\"filename\": \"statement.pdf\", \"fileSizeBytes\": 2097152}]}"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
```

Or using a JSON payload file:

```bash
aws lambda invoke \
  --function-name pii-submit-dev \
  --payload file://payload.json \
  --cli-binary-format raw-in-base64-out \
  response.json
```

---

## Pipeline Coordination (Submit vs UploadWatcher)

- **Submit**: Only validates the batch, mints the ticket, sets DynamoDB status to `AWAITING_UPLOAD` with `expected_file_count`, and returns presigned PUT URLs. **Submit deliberately does NOT trigger Step Functions.**
- **UploadWatcher**: Listens to S3 `ObjectCreated` events under `uploads/`. Once the count of uploaded PDFs under `uploads/<ticketId>/` matches `expected_file_count`, UploadWatcher idempotently changes `job_status` from `AWAITING_UPLOAD` to `PROCESSING` and starts Step Functions execution named `<ticketId>` with input `{ "input-s3-uri": "s3://<bucket>/uploads/<ticketId>" }`.
