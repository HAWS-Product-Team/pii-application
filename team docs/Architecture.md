# Personal Inflation Index - Solutions Architecture

## High-Level Architecture Diagram
```text
┌─────────────────────────┐
│   Amplify / React App   │
└───────────┬─────────────┘
            │  HTTPS (Bearer JWT in Authorization header)
            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                              API Gateway                               │
│                                                                        │
│   JWT Authorizer  ──► validates JWT signature via OIDC JWKS,           │
│                       extracts user context                            │
│                                                                        │
│   POST /submit    ──► generates ticketId, provides S3 presigned URL,   │
│                       starts Step Functions (executionName = ticketId) │
│                                                                        │
│   GET  /status    ──► DynamoDB GetItem (direct integration)            │
└─────┬────────────────────────────────────────────────────┬───────────┘
      │                                                    │
      │ executionName = ticketId                           │ key = ticketId
      │ (free idempotency)                                 │ (mapping template)
      ▼                                                    ▼
┌─────────────────────────────────────────┐      ┌──────────────────────────┐
│             Step Functions              │      │         DynamoDB         │
│             (state machine)             │      │     PAY_PER_REQUEST      │
│                                         │      │                          │
│   pdf2csv ─► merge ─► anonymize         │      │   PK: ticketId           │
│   ─► classify ─► calculate ─► complete  │─────►│   status                 │
│                                         │write │   currentStage           │
│   (updates stage status directly)       │      │   resultS3Uri            │
│                                         │      │   TTL (24h)              │
└─────────────────────────────────────────┘      └──────────────────────────┘

Two paths, one row:
  • Step Functions WRITES status directly to DynamoDB as pipeline stages progress
  • GET /status READS status directly from DynamoDB — no Lambda compute in the read path
  • Complete separation of concerns: asynchronous execution engine and low-latency reader
```

---

### Pipeline Orchestration
```text
        ┌──────────────────────────────────────────────────────────────────┐
        │  AWS STEP FUNCTIONS - Pipeline Orchestrator                      │
        │  ┌────────────────────────────────────────────────────────────┐  │
        │  │ State Machine (staged data pipeline):                      │  │
        │  │                                                            │  │
        │  │  [1] pdf2csv         → Lambda                              │  │
        │  │        │                 (extracts CSV from 1-15MB PDF)    │  │
        │  │        ▼                                                   │  │
        │  │  [2] Normalize/Merge → Lambda                              │  │
        │  │        │                 (cleans & structures transactions)│  │
        │  │        ▼                                                   │  │
        │  │  [3] Anonymize       → Lambda                              │  │
        │  │        │                 (removes sensitive PII data)      │  │
        │  │        ▼                                                   │  │
        │  │  [4] Classify        → ECS Fargate / Lambda                │  │
        │  │        │                 (TF-IDF + ML category inference)  │  │
        │  │        ▼                                                   │  │
        │  │  [5] Calculate       → Lambda                              │  │
        │  │        │                 (computes inflation & weights)    │  │
        │  │        ▼                                                   │  │
        │  │  [6] Update Complete → DynamoDB Task                       │  │
        │  │                          (writes COMPLETED + resultS3Uri)  │  │
        │  │                                                            │  │
        │  │ Each stage reads its input artifact from S3 and writes     │  │
        │  │ output artifacts to S3. Step Functions passes S3 URIs      │  │
        │  │ between states and updates DynamoDB stage markers.         │  │
        │  │ On error → transitions to ErrorHandler (writes FAILED).    │  │
        │  └────────────────────────────────────────────────────────────┘  │
        └──────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
                              S3 STORAGE LAYER
═══════════════════════════════════════════════════════════════════════════════

        ┌────────────────────────────────┐    ┌────────────────────────────────┐
        │  S3 Input / Pipeline Bucket    │    │  S3 Results Bucket             │
        │ (pii-data-pipeline-input-<env>)│    │ (pii-data-pipeline-output-<env>)│
        │                                │    │                                │
        │ Path: /uploads/{ticketId}/     │    │ Path: /results/{ticketId}/     │
        │        input.pdf (1-15MB)      │    │        output.json             │
        │ Lifecycle: Delete after 1 day  │    │ Lifecycle: Delete after 30 days│
        └────────────────────────────────┘    └────────────────────────────────┘
```

---

## Component Details

### 1. Amplify / React Web App

- **Role:** Client user interface for document submission and inflation visualization.
- **Responsibilities:**
  - Authenticate user against the OIDC Identity Provider to acquire a valid JWT.
  - Call `POST /submit` to register the upload request and receive a unique `ticketId` and an S3 presigned PUT URL.
  - Upload the raw PDF document (1 MB to 15 MB) directly to S3 via the presigned URL.
  - Poll `GET /status?ticketId={ticketId}` every 5 seconds to track real-time pipeline status.
  - Retrieve and render the final inflation metrics, category breakdown charts, and spending weights upon job completion.
- **AWS Access:** Direct browser upload to S3 via temporary presigned URLs; all API interactions authenticated via Bearer JWT.

---

### 2. API Gateway

- **Role:** Managed API entry point with token validation and direct serverless integrations.
- **Authorizer:** JWT Authorizer configured with standard OpenID Connect (OIDC) / OAuth2 JSON Web Key Sets (JWKS) issuer and audience verification.
- **Endpoints:**
  
  ```text
  POST /submit
    Headers:  Authorization: Bearer <JWT>
    Request:  { "filename": "statement.pdf", "fileSizeBytes": 5242880 }
    Response: {
      "ticketId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "uploadUrl": "https://pii-data-pipeline-input-<env>.s3.amazonaws.com/uploads/a1b2c3d4.../input.pdf?AWSAccessKeyId=...",
      "status": "PENDING",
      "estimatedSeconds": 45
    }

  GET /status?ticketId={ticketId}
    Headers:  Authorization: Bearer <JWT>
    Response: {
      "ticketId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "status": "COMPLETED | IN_PROGRESS | FAILED",
      "currentStage": "CALCULATING",
      "resultS3Uri": "s3://pii-data-pipeline-output-<env>/results/a1b2c3d4.../output.json",
      "updatedAt": "2026-09-13T17:30:00Z"
    }
  ```

- **Direct Integrations:**
  - `POST /submit`: Invokes an ingestion helper (or native VTL mapping) to generate `ticketId`, write the initial `PENDING` record into DynamoDB, generate the S3 presigned PUT URL, and trigger Step Functions execution.
  - `GET /status`: Direct DynamoDB `GetItem` integration via mapping template (`key = { "ticketId": { "S": "$input.params('ticketId')" } }`). Zero intermediate compute required for status queries.
- **Security & Limits:**
  - CORS enabled for frontend domain.
  - API Gateway throttling (e.g., 100 requests/sec with burst capacity of 200).

---

### 3. DynamoDB State Table

- **Table Name:** `pii-job-status-<env>`
- **Billing Mode:** `PAY_PER_REQUEST` (On-Demand Capacity)
- **Primary Key:** `ticketId` (String, Partition Key)
- **Schema Attributes:**
  - `ticketId` (String): Unique UUID for the processing job.
  - `userId` (String): Subject identifier from JWT claims.
  - `status` (String): `PENDING` | `CONVERTING_PDF` | `NORMALIZING` | `CLASSIFYING` | `CALCULATING` | `COMPLETED` | `FAILED`
  - `currentStage` (String): Human-readable name of the executing step.
  - `resultS3Uri` (String, optional): S3 location of the completed calculation output.
  - `errorMessage` (String, optional): Diagnostics populated on processing failure.
  - `createdAt` (String): ISO 8601 timestamp.
  - `updatedAt` (String): ISO 8601 timestamp.
  - `ttl` (Number): Epoch timestamp set to 24 hours from creation for automatic item expiration.

---

### 4. AWS Step Functions State Machine

- **Role:** End-to-end pipeline orchestrator managing data transformation stages, state transitions, retries, and failure states.
- **Execution Name:** `ticketId` (enforces native idempotency; duplicate triggers for the same ticket cannot create parallel executions).
- **Stage Progression:**
  1. **`UpdateStatus_Converting`**: DynamoDB Task updates `status` to `CONVERTING_PDF`.
  2. **`Pdf2CsvStage`**: Invokes `pdf2csv` Lambda. Converts 1MB–15MB PDF from `uploads/{ticketId}/input.pdf` into tabular CSV `pipeline/{ticketId}/extracted.csv`.
  3. **`UpdateStatus_Normalizing`**: DynamoDB Task updates `status` to `NORMALIZING`.
  4. **`NormalizeMergeStage`**: Invokes `merge` Lambda. Cleans date formats, standardizes currency values, and produces `pipeline/{ticketId}/normalized.csv`.
  5. **`AnonymizeStage`**: Invokes `anonymize` Lambda. Masks personal identifiers and accounts, creating `pipeline/{ticketId}/anonymized.csv`.
  6. **`UpdateStatus_Classifying`**: DynamoDB Task updates `status` to `CLASSIFYING`.
  7. **`ClassifyStage`**: Dispatches ML classification task (`inflation-classifier` container/worker). Evaluates transaction descriptions via pre-loaded TF-IDF model and writes `pipeline/{ticketId}/classified.csv`.
  8. **`UpdateStatus_Calculating`**: DynamoDB Task updates `status` to `CALCULATING`.
  9. **`CalculateStage`**: Invokes `PIICalculator` Lambda. Computes personal inflation rates across 6-month and 12-month windows and spending category breakdowns. Outputs final JSON payload to `results/{ticketId}/output.json`.
  10. **`UpdateStatus_Completed`**: DynamoDB Task sets `status` to `COMPLETED` and records `resultS3Uri`.
- **Error Handling:**
  - Each task defines native `Retry` policies (exponential backoff) for transient errors.
  - Global `Catch` handler routes unexpected exceptions to `UpdateStatus_Failed`, recording `status = "FAILED"` and the exception message into DynamoDB.

---

### 5. Pipeline Compute Modules

#### Module: `pdf2csv`
- **Runtime:** AWS Lambda (Python 3.12)
- **Input:** `s3://pii-data-pipeline-input-<env>/uploads/{ticketId}/input.pdf`
- **Output:** `s3://pii-data-pipeline-input-<env>/pipeline/{ticketId}/extracted.csv`
- **Memory/Timeout:** 1024MB, 60 seconds

#### Module: `merge` / Normalize
- **Runtime:** AWS Lambda (Python 3.12)
- **Input:** Extracted CSV artifact
- **Output:** Normalized transaction schema CSV
- **Memory/Timeout:** 512MB, 30 seconds

#### Module: `inflation-classifier`
- **Runtime:** ECS Fargate Task / High-Memory Lambda
- **Model:** Pre-packaged TF-IDF vectorizer + Logistic Regression classifier baked into container image.
- **Input:** Normalized & anonymized transaction CSV
- **Output:** Classified transaction items with category tags
- **Configuration:** 1 vCPU, 2GB Memory

#### Module: `PIICalculator`
- **Runtime:** AWS Lambda (Python 3.12)
- **Input:** Classified CSV transactions
- **Output:** `s3://pii-data-pipeline-output-<env>/results/{ticketId}/output.json`
- **Memory/Timeout:** 512MB, 30 seconds

---

### 6. S3 Storage Architecture

#### Input & Pipeline Bucket (`pii-data-pipeline-input-<env>`)
- **Key Prefixes:**
  - `/uploads/{ticketId}/input.pdf`: Raw uploaded statements (1MB–15MB).
  - `/pipeline/{ticketId}/*`: Intermediate CSV and JSON artifacts passed between pipeline stages.
- **Lifecycle Policy:** Automatically delete all objects after 1 day (or immediate cleanup post-execution).

#### Results Bucket (`pii-data-pipeline-output-<env>`)
- **Key Prefix:** `/results/{ticketId}/output.json`
- **Payload Schema:**
  
  ```json
  {
    "ticketId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "COMPLETED",
    "generatedAt": "2026-09-13T17:35:00Z",
    "metrics": {
      "personalInflationRate12M": 0.047,
      "personalInflationRate6M": 0.032,
      "categoryBreakdown": {
        "groceries": 0.062,
        "housing": 0.018,
        "transportation": 0.035,
        "electronics": -0.005
      },
      "spendingWeights": {
        "groceries": 0.40,
        "housing": 0.35,
        "transportation": 0.15,
        "electronics": 0.10
      }
    }
  }
  ```
- **Lifecycle Policy:** Automatically expire and delete result artifacts after 30 days.

---

## Data Flow - Happy Path

```text
1. User Initiates Upload:
   • Frontend issues POST /submit with JWT in Authorization header.
   • API Gateway validates JWT and creates DynamoDB record with status="PENDING".
   • Returns { ticketId, uploadUrl, estimatedSeconds: 45 }.

2. Direct S3 Upload:
   • Frontend performs HTTP PUT of the PDF (1MB–15MB) directly to S3 via presigned uploadUrl.
   • Upload completes without traversing intermediate compute or API payload limits.

3. Pipeline Execution:
   • Step Functions starts execution with executionName = ticketId.
   • pdf2csv Lambda extracts tabular data from PDF to CSV.
   • merge & anonymize Lambdas normalize and sanitize data.
   • inflation-classifier infers expense categories.
   • PIICalculator computes index values and generates output.json in S3 results bucket.

4. Status Tracking:
   • Step Functions writes stage updates directly to DynamoDB (CONVERTING_PDF -> CLASSIFYING -> CALCULATING -> COMPLETED).
   • Frontend polls GET /status?ticketId={ticketId} every 5 seconds.
   • API Gateway reads directly from DynamoDB via GetItem (sub-10ms response, no Lambda invocation).

5. Result Display:
   • Frontend detects status="COMPLETED", retrieves calculation metrics, and renders interactive inflation reports.

6. Automatic Lifecycle Cleanup:
   • DynamoDB item expires automatically after 24 hours via DynamoDB TTL.
   • Raw uploaded PDFs and intermediate pipeline files expire after 1 day via S3 Lifecycle.
   • Final calculation results expire after 30 days via S3 Lifecycle.
```

---

## Data Flow - Error Path

```text
1. Processing Failure:
   • An invalid PDF format, corrupted transaction line, or execution timeout occurs during a pipeline stage.
   • Step Functions retry attempts are exhausted.

2. Automated Error Handling:
   • Step Functions Catch block intercepts the error.
   • Step Functions executes direct DynamoDB UpdateItem:
       status = "FAILED"
       errorMessage = "Failed to extract tabular data from uploaded PDF"

3. Client Notification:
   • On the next polling cycle (GET /status?ticketId={ticketId}), API Gateway returns status="FAILED" and the error message.
   • Frontend presents user-friendly error diagnostics and prompt to re-upload.
```

---

## Authentication & Security

- **Token Validation:** API Gateway JWT Authorizer validates token signatures against the OIDC Provider's public JWKS endpoint on every request.
- **S3 Presigned URLs:**
  - Restricted to specific key path (`uploads/{ticketId}/input.pdf`).
  - Short expiration window (15 minutes).
  - Restricts HTTP verb strictly to `PUT`.
- **Identity Isolation:** The `ticketId` and `userId` mapping in DynamoDB ensures users can only query status for tickets associated with their identity.
- **Serverless IAM Principles:**
  - API Gateway has strict `dynamodb:GetItem` permission limited to the status table.
  - Step Functions state machine execution role is restricted to invoking designated Lambda functions and performing `dynamodb:UpdateItem` on the status table.
  - Compute workers have least-privilege read/write access limited to pipeline bucket prefixes.
- **Encryption:**
  - All external and inter-service communications enforce TLS 1.2+.
  - S3 buckets enforce server-side encryption (`AES256` / `aws:kms`).
  - DynamoDB uses AWS-managed KMS encryption at rest.

---

## Monitoring, Logging & Observability

- **CloudWatch Metrics:**
  - API Gateway 4xx/5xx error rates, latency (p95, p99), and integration latency.
  - Step Functions executions started, succeeded, failed, and execution duration.
  - Lambda duration, invocations, throttles, and error rates.
  - DynamoDB consumed read/write units and throttled requests.
- **Structured Logging & Tracing:**
  - CloudWatch Logs enabled with 14-day retention across all Lambda functions and Step Functions execution logs.
  - AWS X-Ray tracing enabled across API Gateway and Step Functions for distributed transaction tracing.
- **CloudWatch Alarms:**
  - Step Functions execution failure alarm (triggers alert on pipeline crash).
  - API Gateway 5xx rate > 1% over 5-minute window.

---

## Cost Optimization Model

The architecture utilizes a pure pay-per-request serverless model to eliminate idle resource expenditures:

| Component | Cost Model | Expected Monthly Impact (1–1,000 active users) |
| :--- | :--- | :--- |
| **API Gateway** | HTTP API ($1.00 / million requests) | < $2.00 |
| **Step Functions** | Standard Workflows ($0.025 / 1,000 transitions) | < $1.50 |
| **AWS Lambda** | Compute per millisecond ($0.0000166667 / GB-s) | < $3.00 |
| **DynamoDB** | On-Demand (PAY_PER_REQUEST, reads/writes + TTL) | < $1.00 |
| **S3 Storage & Transfer**| Standard Storage + Lifecycle transitions | < $2.00 |
| **Total Estimated Cost**| **100% Usage-Proportional (Zero Idle Compute)** | **~$5.00 – $15.00 / month** |

---

## Deployment Checklist

- [ ] Configure Generic OIDC / OAuth2 JWT Authorizer in API Gateway with Issuer and Audience.
- [ ] Create DynamoDB state table `pii-job-status-<env>` with `PAY_PER_REQUEST` billing and enable TTL on attribute `ttl`.
- [ ] Create S3 buckets (`pii-data-pipeline-input-<env>`, `pii-data-pipeline-output-<env>`) with lifecycle policies (1-day input expiration, 30-day output expiration).
- [ ] Deploy Lambda functions (`pdf2csv`, `merge`, `anonymize`, `PIICalculator`).
- [ ] Build and publish ML classification image (`inflation-classifier`) to Amazon ECR.
- [ ] Deploy Step Functions state machine with stage transitions, DynamoDB update tasks, and catch/retry blocks.
- [ ] Configure API Gateway routes (`POST /submit`, `GET /status`) with direct integrations.
- [ ] Configure CloudWatch alarms for Step Functions failures and API Gateway 5xx error rates.
- [ ] Perform end-to-end integration validation (PDF upload ➔ S3 presigned PUT ➔ Step Functions execution ➔ DynamoDB direct read ➔ results rendering).
