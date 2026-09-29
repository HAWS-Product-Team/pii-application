# Personal Inflation Index - Solutions Architecture
PII is a stateless tool that returns to the user insight about their financial situation.  We don't authenticate
the user anymore than a mortage calculater requires that step.

## High-Level Architecture Diagram
```text
┌─────────────────────────┐
│   Amplify / React App   │
└───────────┬─────────────┘
            │  HTTPS (Bearer token <ticket>.<secret> in Authorization header)
            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                              API Gateway                               │
│   GET /                    ──► welcome & info                          │
│   POST /spending-history   ──► accepts upload request, returns ticket  │
│                                and presigned URL, writes to DynamoDB   │
│   GET  /pii-report-status  ──► checks processing status via DynamoDB   │
│   GET  /pii-report         ──► retrieves calculation report from S3    │
│   Custom Authorizer        ──► validates token against DynamoDB hash   │
└─────┬────────────────────────────────────────────────────┬─────────────┘
      ▼                                                    │
 ┌──────────────────────────────────────────────────┐      │
 │ UploadWatcher ──► Starts pipeline when expected  │      │
 │                   uploads have landed in S3.     │      │
 └─────┬────────────────────────────────────────────┘      │
   starts execution: {ticket, uploads,                     │ key = ticketId
       │              inputCsv, classifiedCsv,             │ (token auth & status)
       │              piiReportJson}                       │
       ▼                                                   ▼
┌─────────────────────────────────────────┐      ┌──────────────────────────┐
│             Step Functions              │      │         DynamoDB         │
│         (data pipeline orchestrator)    │      │     PAY_PER_REQUEST      │
│                                         │      │                          │
│   Normalize ──► Merge ──►               │      │   PK: ticketId           │
│   Classify (Batch) ──► CalculatePII     │      │   secretHash             │
│                                         │      │   status                 │
│   (orchestrates Lambdas & AWS Batch,    │      │   TTL (24h)              │
│    accumulates results via ResultPath)  │      │                          │
└─────────────────────────────────────────┘      └──────────────────────────┘
```

---

### Pipeline Orchestration
```text
        ┌──────────────────────────────────────────────────────────────────┐
        │  AWS STEP FUNCTIONS - Pipeline Orchestrator                      │
        │  ┌────────────────────────────────────────────────────────────┐  │
        │  │ State Machine (staged data pipeline):                      │  │
        │  │                                                            │  │
        │  │  [1] Normalize       → Lambda (pdf2csv)                    │  │
        │  │        │                 (extracts CSVs from PDF uploads)  │  │
        │  │        ▼                                                   │  │
        │  │  [2] Merge           → Lambda                              │  │
        │  │        │                 (combines CSVs to purchase_data)  │  │
        │  │        ▼                                                   │  │
        │  │  [3] Classify        → AWS Batch (Fargate ARM64)           │  │
        │  │        │                 (sync job classify-{ticket})      │  │
        │  │        ▼                                                   │  │
        │  │  [4] CalculatePII    → Lambda                              │  │
        │  │                          (computes PII report JSON)        │  │
        │  │                                                            │  │
        │  │ Each stage reads its input artifact from S3 and writes     │  │
        │  │ output artifacts to S3. Step Functions coordinates JSON    │  │
        │  │ payload parameters (uploads, inputCsv, classifiedCsv,      │  │
        │  │ piiReportJson) and manages retries with exponential backoff│  │
        │  └────────────────────────────────────────────────────────────┘  │
        └──────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
                              S3 STORAGE LAYER
═══════════════════════════════════════════════════════════════════════════════

        ┌────────────────────────────────┐    ┌────────────────────────────────┐
        │  S3 Input / Pipeline Bucket    │    │  S3 Results Bucket             │
        │ (pii-data-pipeline-input-<env>)│    │ (pii-data-pipeline-output-<env>)│
        │                                │    │                                │
        │ Path: /{ticketId}/uploads/     │    │ Path: /{ticketId}/             │
        │        input PDFs & parsed CSVs│    │        pii-report.json         │
        │ Path: /{ticketId}/             │    │                                │
        │        purchase_data.csv       │    │                                │
        │        classified.csv          │    │                                │
        │ Path: /lambdas/*.zip           │    │                                │
        │ Lifecycle: Delete after 2 days │    │ Lifecycle: Delete after 14 days│
        └────────────────────────────────┘    └────────────────────────────────┘
```

---

## Component Details

### 1. Amplify / React Web App

- **Role:** Client user interface for document submission and inflation visualization.
- **Responsibilities:**
  - Authenticate user requests using a bearer token (`<ticket>.<secret>`) where the secret is verified against a hashed secret stored in DynamoDB.
  - Call `POST /spending-history` to register the upload request and receive a unique numeric `ticket` (e.g., `123456789`), a secret token, and an S3 presigned PUT URL.
  - Upload raw PDF statements (1 MB to 15 MB) directly to S3 (`{ticket}/uploads/`) via the presigned URL.
  - Poll `GET /pii-report-status` using `Authorization: Bearer <ticket>.<secret>` to track real-time pipeline status.
  - Retrieve and render the final inflation metrics, category breakdown charts, and spending weights upon job completion (`GET /pii-report`).
- **AWS Access:** Direct browser upload to S3 via temporary presigned URLs; all subsequent API interactions authenticated via custom Bearer token.

---

### 2. API Gateway

- **Role:** Managed API entry point with custom token authorizer, and direct serverless integrations.
- **Authorizer:** Custom Lambda Authorizer (`BearerAuth`, `nodejs18.x`) validates that the requestor's Bearer token (`<ticket>.<secret>`) secret, when hashed, matches the hash stored in DynamoDB for that ticket.
- **Endpoints:**
  
  ```text
  GET /
    Welcome / landing page endpoint.

  POST /spending-history
    Headers:  Content-Type: application/json
    Request:  [
  { "filename": "statement.pdf", "fileSizeBytes": 5242880 },
  { "filename": "statement2.pdf", "fileSizeBytes": 5242880 },
  ]
    Response: {
      "ticket": "123456789",
      "secret": "a1b2c3d4e5f67890abcdef1234567890",
      [
        "uploadUrl": "https://pii-data-pipeline-input-<env>.s3.amazonaws.com/123456789/uploads/statement.pdf?AWSAccessKeyId=...",
        "uploadUrl": "https://pii-data-pipeline-input-<env>.s3.amazonaws.com/123456789/uploads/statement2.pdf?AWSAccessKeyId=...",
      ],
      "job_status": "PENDING",
      "estimatedSeconds": 45
    }

  GET /pii-report-status
    Headers:  Authorization: Bearer <ticket>.<secret>
    Response: {
      "ticket": "123456789",
      "job_status": "COMPLETED | IN_PROGRESS | FAILED",
      "updatedAt": "2026-09-28T15:00:00Z"
    }

  GET /pii-report
    Headers:  Authorization: Bearer <ticket>.<secret>
    Response: {
      "ticket": "123456789",
      "job_status": "COMPLETED",
      "report": { ... }
    }
  ```

- **Direct Integrations & Messaging:**
  - `POST /spending-history`: Interacts with backend ticket minting, provides presigned S3 upload URLs, 
  and puts ticket and secret in DynamoDB.
  - `GET /pii-report-status` & `GET /pii-report`: Protected by `BearerAuth` custom Lambda authorizer.
- **Security & Limits:**
  - CORS enabled for frontend domain.
  - API Gateway throttling and logging configured per stage.

---

### 3. DynamoDB State Table

- **Table Name:** `pii-job-status-<env>`
- **Billing Mode:** `PAY_PER_REQUEST` (On-Demand Capacity)
- **Primary Key:** `ticketId` (String, Partition Key)
- **Schema Attributes:**
  - `ticket_id` (String): Unique numeric ticket ID (e.g., `123456789`).
  - `secret_hash` (String): Cryptographic hash of the ticket secret for token authentication.
  - `expected_file_count` (Number): number of files expected to be uploaded. 
  - `job_status` (String): `AWAITING_UPLOAD` | `PROCESSING` | `COMPLETED` | `FAILED`
  - `expires_at` (Number): Epoch timestamp set to 24 hours from creation for automatic item expiration.
  - `created_at` (String): ISO 8601 timestamp.

---

### 4. AWS Step Functions State Machine

- **Role:** Orchestrates the end-to-end data pipeline: Normalizer (Lambda), Merge (Lambda), Classifier (AWS Batch on Fargate ARM64), and PII Calculator (Lambda).
- **State Machine Resource:** `${app_name}-data-pipeline-${environment}`
- **Execution Role:** `${app_name}-step-functions-role-${environment}`
- **Input Execution Contract:**
  The state machine is triggered with a JSON payload containing the ticket and S3 artifact locations:

  ```json
  {
    "ticket": "123456789",
    "uploads": "s3://pii-data-pipeline-input-dev/123456789/uploads",
    "inputCsv": "s3://pii-data-pipeline-input-dev/123456789/purchase_data.csv",
    "classifiedCsv": "s3://pii-data-pipeline-input-dev/123456789/classified.csv",
    "piiReportJson": "s3://pii-data-pipeline-output-dev/123456789/pii-report.json"
  }
  ```

- **Stages & State Transitions:**

  ```text
  [Start] ──► Normalize (Lambda) ──► Merge (Lambda) ──► Classify (Batch Sync) ──► CalculatePII (Lambda) ──► [End]
  ```

  1. **`Normalize`** (`Task: arn:aws:states:::lambda:invoke`)
     - **Target Function:** `aws_lambda_function.normalizer` (`${app_name}-normalizer-${environment}`)
     - **Payload:**
       ```json
       {
         "input-s3-uri.$": "$.uploads",
         "output-s3-uri.$": "$.uploads"
       }
       ```
     - **ResultPath:** `$.normalizerResult`
     - **Retry Policy:**
       - Errors: `Lambda.ServiceException`, `Lambda.AWSLambdaException`, `Lambda.SdkClientException`, `Lambda.TooManyRequestsException`
       - `IntervalSeconds`: 2, `MaxAttempts`: 3, `BackoffRate`: 2.0
     - **Next:** `Merge`
     - **Description:** Invokes the PDF parser (`pdf2csv`) to extract tabular transaction data from all uploaded PDF statements in `$.uploads` and writes individual CSV files back to `$.uploads`.

  2. **`Merge`** (`Task: arn:aws:states:::lambda:invoke`)
     - **Target Function:** `aws_lambda_function.merge` (`${app_name}-merge-${environment}`)
     - **Payload:**
       ```json
       {
         "ticket.$": "$.ticket",
         "input-s3-uri.$": "$.uploads",
         "output-s3-uri.$": "$.inputCsv"
       }
       ```
     - **ResultPath:** `$.mergeResult`
     - **Retry Policy:** Same Lambda transient exception retry policy (`IntervalSeconds`: 2, `MaxAttempts`: 3, `BackoffRate`: 2.0).
     - **Next:** `Classify`
     - **Description:** Consolidates all individual CSV files found in `$.uploads` into a single unified transaction CSV (`purchase_data.csv`) saved to `$.inputCsv`.

  3. **`Classify`** (`Task: arn:aws:states:::batch:submitJob.sync`)
     - **Target:** AWS Batch Fargate Job Definition (`${app_name}-batch-jobdef-fargate-${environment}`) on Job Queue (`${app_name}-batch-queue-${environment}`)
     - **Parameters:**
       ```json
       {
         "JobName.$": "States.Format('classify-{}', $.ticket)",
         "JobQueue": "${aws_batch_job_queue.batch_queue.arn}",
         "JobDefinition": "${aws_batch_job_definition.batch_job.arn}",
         "Parameters": {
           "input_s3_uri.$": "$.inputCsv",
           "output_s3_uri.$": "$.classifiedCsv"
         }
       }
       ```
     - **ResultPath:** `$.batchResult`
     - **Retry Policy:**
       - Errors: `Batch.AWSBatchException`
       - `IntervalSeconds`: 30, `MaxAttempts`: 2, `BackoffRate`: 2.0
     - **Next:** `CalculatePII`
     - **Description:** Submits a synchronous AWS Batch job on Fargate ARM64. The containerized ML classifier processes `purchase_data.csv` to predict CPI spending categories and outputs `classified.csv` to `$.classifiedCsv`.

  4. **`CalculatePII`** (`Task: arn:aws:states:::lambda:invoke`)
     - **Target Function:** `aws_lambda_function.pii_calculator` (`${app_name}-pii-calculator-${environment}`)
     - **Payload:**
       ```json
       {
         "ticket.$": "$.ticket",
         "input-s3-uri.$": "$.classifiedCsv",
         "output-s3-uri.$": "$.piiReportJson"
       }
       ```
     - **ResultPath:** `$.lambdaResult`
     - **Retry Policy:** Same Lambda transient exception retry policy (`IntervalSeconds`: 2, `MaxAttempts`: 3, `BackoffRate`: 2.0).
     - **End:** `true`
     - **Description:** Ingests `classified.csv`, calculates category weights and personal inflation rates across 
     6-month and 12-month periods, and outputs `pii-report.json` to the S3 results bucket.

- **State Machine Logging & Tracing:**
  - **CloudWatch Log Group:** `/aws/vendedlogs/states/${app_name}-data-pipeline-${environment}`
  - **Logging Level:** `ALL`
  - **Include Execution Data:** `true`
  - **Retention:** 3 days (configurable via `step_functions_log_retention_days`)

---

### 5. Pipeline Compute Modules

#### Module: `pdf2csv` (Normalizer)
- **Runtime:** AWS Lambda (`python3.12`, `arm64`)
- **Handler:** `pdf2csv.lambda_handler.handler`
- **Memory / Timeout:** 1536 MB, 180 seconds
- **Ephemeral Storage (/tmp):** 5120 MB (5 GB)
- **Deployment Artifact:** `s3://pii-data-pipeline-input-<env>/lambdas/normalizer.zip`
- **Input:** `s3://pii-data-pipeline-input-<env>/{ticket}/uploads`
- **Output:** Individual parsed CSVs written to `s3://pii-data-pipeline-input-<env>/{ticket}/uploads`

#### Module: `merge`
- **Runtime:** AWS Lambda (`python3.12`, `arm64`)
- **Handler:** `merge.lambda_handler.handler`
- **Memory / Timeout:** 512 MB, 60 seconds
- **Deployment Artifact:** `s3://pii-data-pipeline-input-<env>/lambdas/merge.zip`
- **Input:** `s3://pii-data-pipeline-input-<env>/{ticket}/uploads`
- **Output:** Consolidated CSV `s3://pii-data-pipeline-input-<env>/{ticket}/purchase_data.csv`

#### Module: `inflation-classifier`
- **Runtime:** AWS Batch on ECS Fargate / Fargate Spot (`arm64`)
- **Compute Environment:** Managed Fargate / Fargate Spot (`max_vcpus = 16`, default `use_fargate_spot = true`)
- **Job Definition:** `${app_name}-batch-jobdef-fargate-${environment}`
- **Container Image:** Amazon ECR repository `${app_name}-classifier-${environment}:latest`
- **Resource Allocation:** 2 vCPU, 4096 MB RAM
- **Job Timeout:** 1800 seconds (30 minutes)
- **Parameters / Command:** Positional arguments `[input_s3_uri, output_s3_uri]`
- **Input:** `s3://pii-data-pipeline-input-<env>/{ticket}/purchase_data.csv`
- **Output:** `s3://pii-data-pipeline-input-<env>/{ticket}/classified.csv`

#### Module: `PIICalculator`
- **Runtime:** AWS Lambda (`python3.12`, `arm64`)
- **Handler:** `piicalculator.lambda_handler.handler`
- **Memory / Timeout:** 256 MB, 300 seconds
- **Deployment Artifact:** `s3://pii-data-pipeline-input-<env>/lambdas/pii-calculator.zip`
- **Input:** `s3://pii-data-pipeline-input-<env>/{ticket}/classified.csv`
- **Output:** `s3://pii-data-pipeline-output-<env>/{ticket}/pii-report.json`

---

### 6. S3 Storage Architecture

#### Input & Intermediate Bucket (`pii-data-pipeline-input-<env>`)
- **Key Prefixes & Files:**
  - `/{ticketId}/uploads/`: Uploaded statements (PDF format, 1MB–15MB) and extracted individual CSVs.
  - `/{ticketId}/purchase_data.csv`: Consolidated transaction CSV output from `merge`.
  - `/{ticketId}/classified.csv`: CPI-categorized transaction CSV output from `inflation-classifier`.
  - `/lambdas/*.zip`: Lambda deployment packages (`normalizer.zip`, `merge.zip`, `pii-calculator.zip`).
- **Security:** Server-side encryption with AES256, public access completely blocked, `BucketOwnerEnforced`.
- **Lifecycle Policy:** Automatically delete objects under prefix `input/` after 2 days (configurable via `input_retention_days`).

#### Results Bucket (`pii-data-pipeline-output-<env>`)
- **Key Prefix:** `/{ticketId}/pii-report.json`
- **Security:** Server-side encryption with AES256, public access completely blocked, `BucketOwnerEnforced`.
- **Lifecycle Policy:** Automatically delete results under prefix `output/` after 14 days (configurable via `output_retention_days`).
- **Payload Schema:**
  
  ```json
  {
    "ticket": "123456789",
    "job_status": "COMPLETED",
    "generatedAt": "2026-09-28T15:00:00Z",
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

---

## Data Flow - Happy Path

```text
1. User Initiates Upload:
   • Frontend issues POST /spending-history.
   • API Gateway / backend mints unique numeric ticket (e.g. 123456789), computes secret token,
     stores the hashed secret in DynamoDB (job_status="PENDING").
   • Returns { ticket, secret, uploadUrl, job_status: "PENDING", estimatedSeconds: 45 }.

2. Direct S3 Upload:
   • Frontend performs HTTP PUT of PDF statement(s) directly to S3 (.../{ticket}/uploads/) via presigned uploadUrl.
   • Upload completes without traversing intermediate compute or API payload limits.

3. UploadWatcher:
    * When the count of files in S3 matches what was expected, sets job_status="processing"
    and starts Pipeline execution.
    
4. Pipeline Execution (Step Functions):
   • Step Functions starts execution with payload:
       { "ticket": "123456789", "uploads": "s3://.../123456789/uploads",
         "inputCsv": "s3://.../123456789/purchase_data.csv",
         "classifiedCsv": "s3://.../123456789/classified.csv",
         "piiReportJson": "s3://.../123456789/pii-report.json" }
   • [1] Normalize Stage: Normalizer Lambda (pdf2csv) converts PDF statements to individual CSVs in uploads.
   • [2] Merge Stage: Merge Lambda consolidates CSVs into purchase_data.csv.
   • [3] Classify Stage: Step Functions submits synchronous AWS Batch job on Fargate ARM64.
         Container classifies transaction rows into 8 CPI categories and outputs classified.csv.
   • [4] CalculatePII Stage: PIICalculator Lambda calculates inflation index rates & category weights,
         writing pii-report.json to the S3 results bucket.

5. Status Tracking:
   • Frontend polls GET /pii-report-status every 5 seconds using Authorization: Bearer <ticket>.<secret>.
   • Custom Lambda Authorizer verifies the hashed secret against DynamoDB.

6. Result Display:
   • Frontend detects job_status="COMPLETED", requests GET /pii-report, and renders interactive inflation visuals.

7. Automatic Lifecycle Cleanup:
   • DynamoDB item expires automatically after 24 hours via DynamoDB TTL.
   • Raw uploaded PDFs and intermediate pipeline files expire after 2 days via S3 Lifecycle.
   • Final calculation results expire after 14 days via S3 Lifecycle.
```

---

## Data Flow - Error Path

```text
1. Processing Failure:
   • An invalid PDF format, corrupted transaction line, container failure, or execution timeout occurs.
   • Step Functions automated retry policies kick in:
       - Lambda stages: Up to 3 retries with 2-second initial interval and 2.0 backoff multiplier.
       - AWS Batch stage: Up to 2 retries with 30-second initial interval and 2.0 backoff multiplier.

2. State Machine Failure:
   • If retries are exhausted, Step Functions marks the execution as FAILED.
   • Complete error diagnostics and step details are logged to CloudWatch Logs:
     /aws/vendedlogs/states/<app_name>-data-pipeline-<env>.

3. Client Notification:
   • On subsequent polling of GET /pii-report-status, job_status returns FAILED.
   • Frontend presents user-friendly error diagnostics and prompts the user to re-upload.
```

---

## Authentication & Security

- **Custom Bearer Token Authorizer:** API Gateway custom Lambda authorizer (`BearerAuth`) validates tokens in
`<ticket>.<secret>` format against the cryptographic hash stored in DynamoDB for that ticket.
- **S3 Presigned URLs:**
  - Restricted to specific key path (`{ticketId}/uploads/`).
  - Short expiration window (15 minutes).
  - Restricts HTTP verb strictly to `PUT`.
- **Identity & Job Isolation:** Every user session receives an isolated numeric ticket and secret token. Pipeline processing and S3 paths are compartmentalized per ticket prefix (`/{ticketId}/`).
- **Serverless IAM Principles:**
  - Step Functions state machine execution role is restricted to invoking designated pipeline Lambdas (`normalizer`, `merge`, `pii_calculator`) and submitting jobs to the specific AWS Batch queue and job definition.
  - AWS Batch execution and job roles have least-privilege access restricted to S3 bucket prefixes, ECR image pull, and CloudWatch log groups.
  - Batch security group strictly restricts outbound egress to HTTPS (port 443), DNS (port 53), and NTP (port 123).
- **Encryption:**
  - All external and inter-service communications enforce TLS 1.2+.
  - S3 buckets enforce server-side encryption (`AES256`).
  - DynamoDB uses AWS-managed KMS encryption at rest.

---

## Monitoring, Logging & Observability

- **CloudWatch Metrics:**
  - API Gateway 4xx/5xx error rates, request latency, and authorizer duration.
  - Step Functions executions started, succeeded, failed, and execution duration.
  - Lambda duration, invocations, throttles, and error rates.
  - AWS Batch runnable time, execution time, and container exit codes.
  - DynamoDB consumed capacity and throttled requests.
- **Structured Logging:**
  - Step Functions execution logs logged to `/aws/vendedlogs/states/${app_name}-data-pipeline-${environment}` with log level `ALL`, `include_execution_data = true`, and 3-day retention.
  - Lambda functions log to `/aws/lambda/${app_name}-<function>-${environment}` with 3-day retention.
  - AWS Batch container logs streamed to `/aws/batch/${app_name}-${environment}`.
- **CloudWatch Alarms:**
  - Step Functions execution failure alarm (alerts on pipeline failures).
  - API Gateway 5xx rate > 1% over 5-minute window.

---

## Cost Optimization Model

The architecture utilizes a pure pay-per-request serverless model to eliminate idle resource expenditures:

| Component | Cost Model | Expected Monthly Impact (1–1,000 active users) |
| :--- | :--- | :--- |
| **API Gateway** | REST API ($3.50 / million requests) | < $2.00 |
| **Step Functions** | Standard Workflows ($0.025 / 1,000 transitions) | < $1.50 |
| **AWS Lambda** | Compute per millisecond on ARM64 Graviton ($0.0000133334 / GB-s) | < $3.00 |
| **AWS Batch** | Managed Fargate Spot ARM64 (70% savings over on-demand Fargate) | < $5.00 |
| **DynamoDB** | On-Demand (`PAY_PER_REQUEST`, reads/writes + TTL) | < $1.00 |
| **S3 Storage & Transfer**| Standard Storage + 2-day input / 14-day output lifecycles | < $2.00 |
| **Total Estimated Cost**| **100% Usage-Proportional (Zero Idle Compute)** | **~$10.00 – $15.00 / month** |

---

## Deployment Checklist

- [ ] Deploy DynamoDB state table `pii-job-status-<env>` with `PAY_PER_REQUEST` billing and enable TTL on attribute `expires_at`.
- [ ] Create S3 buckets (`pii-data-pipeline-input-<env>`, `pii-data-pipeline-output-<env>`) with 
lifecycle policies (2-day input expiration, 14-day output expiration).
- [ ] Build and upload Lambda deployment packages (`normalizer.zip`, `merge.zip`, `pii-calculator.zip`) to
`s3://pii-data-pipeline-input-<env>/lambdas/`.
- [ ] Deploy Lambda functions (`normalizer`, `merge`, `pii_calculator`, and custom authorizer).
- [ ] Build and push ML classification image (`inflation-classifier`) to Amazon ECR.
- [ ] Provision AWS Batch compute environment (Fargate Spot ARM64), job queue, and job definition.
- [ ] Deploy Step Functions State Machine orchestrating `Normalize` ➔ `Merge` ➔ `Classify` ➔ `CalculatePII`.
- [ ] Configure API Gateway REST API, `BearerAuth` Lambda Authorizer, DynamoDB, and endpoint routes.
- [ ] Configure CloudWatch log groups (3-day retention) and failure alarms.
- [ ] Perform end-to-end integration validation (PDF upload ➔ S3 presigned PUT ➔ Step Functions execution ➔
- [ ] Bucket notification rule for ObjectCreated under uploads/
Batch classification ➔ PII calculation ➔ Results verification).
