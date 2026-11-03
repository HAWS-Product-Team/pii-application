# Story: Check Ticket Lambda Authorizer (REST API Custom Authorizer)

## Summary
**As a** user,
**I want** requests to protected spending-history endpoints to be validated against my ticket ID and secret,
**so that** my financial reports and status remain private and accessible only to me.

This story implements the **API Gateway custom Lambda authorizer** (`check_ticket`). It intercepts incoming calls to 
protected REST API endpoints, validates the caller's credentials against DynamoDB, and generates an IAM policy 
granting or denying access.

---

## Background & Architecture

The PII application uses ticket-based bearer credentials rather than traditional user accounts:
1. `POST /spending-history` (Submit handler) mints a ticket and returns a `ticketId` (ULID) and a raw `secret` 
(base64url) once to the user.
2. Direct S3 uploads (`PUT uploads/<ticketId>/...`) are authorized via presigned URLs and do not transit API Gateway.
3. Subsequent API calls requesting processing status or report artifacts require API Gateway authorization.

### Endpoint Authorization Classification
- **Public / Unauthenticated:**
  - `GET /` (Welcome / edification page)
  - `POST /spending-history` (Session creation / ticket minting)
- **Protected by Authorizer:**
  - `GET /pii-report-status`
  - `GET /pii-report`
  - Any future endpoints exposing ticket-backed data

---

## Lambda Configuration & Environment Variables

| Parameter | Value | Notes |
|---|---|---|
| **Runtime** | `python3.12` | Python 3.12 matching project standard |
| **Architecture** | `arm64` | AWS Graviton2 / Linux |
| **Handler** | `check_ticket.lambda_handler.handler` | Module entrypoint |
| **Memory** | `256 MB` | Fast execution with minimal memory footprint |
| **Timeout** | `10 seconds` | Tight SLA for API Gateway authorizers |
| **Ephemeral Storage (/tmp)** | `512 MB` | Default |

### Environment Variables
- `TICKETS_TABLE_NAME` *(required, string)*: DynamoDB table name storing tickets (e.g. `pii-tickets-dev`).

---

## Authorization Header Contract

The client must supply credentials in the HTTP `Authorization` header using the strict `Ticket` scheme:

```http
Authorization: Ticket <ticket_id>:<secret>
```

Example:
```http
Authorization: Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A
```

### Parsing Rules:
- Header name: Strictly `Authorization`.
- Scheme: Strictly `Ticket` (case-sensitive, followed by a single space).
- Credential format: `<ticket_id>:<secret>` delimited by the first colon (`:`).
- `ticket_id`: Must be a valid 26-character canonical ULID 
(Crockford Base32 alphabet: `0123456789ABCDEFGHJKMNPQRSTVWXYZ`, case-insensitive).
- `secret`: Non-empty base64url-encoded string without padding.
- Malformed headers, missing values, or unrecognized schemes fail immediately with an unauthorized error.

---

## Validation Logic & Flow

The authorizer Lambda executes the following sequential steps:

1. **Header Extraction & Validation:**
   - Extract `Authorization` header from the authorizer event (supporting both Token and Request authorizer event shapes).
   - Enforce the strict `Ticket <ticket_id>:<secret>` format.
   - If missing, empty, or malformed, reject immediately (raise `Unauthorized`).

2. **DynamoDB Ticket Lookup:**
   - Fetch the item from `TICKETS_TABLE_NAME` where partition key `ticket_id = <ticket_id>`.
   - Use low-level client `get_item` or resource with projection for `ticket_id`, `secret_hash`, and `expires_at`.
   - If no record exists, reject immediately (raise `Unauthorized`).

3. **Expiration Check:**
   - Read `expires_at` (epoch seconds stored as a numeric attribute).
   - Compare against current UTC timestamp (`datetime.now(UTC).timestamp()`).
   - If `current_time >= expires_at`, the ticket is expired: reject immediately (raise `Unauthorized`).

4. **Secret Hash Verification:**
   - Verify the presented `secret` against the stored `secret_hash`.
   - Use the shared verification utility from the minting module (`verify_secret(secret, stored_secret_hash)`):
     - Decode the base64url secret back to raw 32 bytes (restoring padding as necessary).
     - Compute SHA-256 hex digest of the raw bytes.
     - Compare the computed digest with `stored_secret_hash` using constant-time comparison (`hmac.compare_digest`) to prevent timing side-channel attacks.
   - Never compare raw plaintext secrets or store unhashed secrets.
   - If hashes do not match, reject immediately (raise `Unauthorized`).

5. **Separation of Concerns (Job Status):**
   - The authorizer is strictly responsible for identity and credential validation.
   - Route-specific workflow constraints based on `job_status` (e.g. denying report download before status is `COMPLETE`) are handled by downstream Lambdas (`pii-report-status`, `pii-report`), **not** by this authorizer.

---

## IAM Policy Generation & Context Injection

Upon successful validation, the authorizer returns an API Gateway IAM policy and authorizer context:

```json
{
  "principalId": "ticket:01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "policyDocument": {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Action": "execute-api:Invoke",
        "Effect": "Allow",
        "Resource": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/*/*"
      }
    ]
  },
  "context": {
    "ticketId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"
  }
}
```

### Policy Scoping for Caching:
- To allow API Gateway authorizer caching (default TTL 300s) without blocking subsequent calls to different endpoints (e.g. calling `/pii-report-status` then `/pii-report`), the `Resource` ARN is generated as a **wildcard stage ARN**:
  - Parse incoming `methodArn` (`arn:aws:execute-api:<region>:<account>:<apiId>/<stage>/<method>/<path>`).
  - Replace `<method>/<path>` with `*/*` (`arn:aws:execute-api:<region>:<account>:<apiId>/<stage>/*/*`).
- This grants the caller access to all authorized endpoints within the API stage for the duration of the cache TTL.

### Context Forwarding:
- `context.ticketId` is injected into the request context.
- Downstream Lambdas (e.g. report status, report generator) read `event.requestContext.authorizer.ticketId` and do not need to re-verify credentials or trust client-supplied ticket query/body parameters.

---

## Error Handling & Failure Semantics

- **Unauthorized Failures (HTTP 401):**
  - For any authentication failure (missing header, malformed header, ticket not found, expired ticket, secret mismatch, or DynamoDB exception), the Lambda raises an `Exception("Unauthorized")`.
  - In AWS API Gateway, raising `"Unauthorized"` instructs API Gateway to return `HTTP 401 Unauthorized` with standard `WWW-Authenticate` response headers.
- **Security & Logging Constraints:**
  - Raw `secret` and the full `Authorization` header must **never** be logged, printed to CloudWatch, or included in error messages.
  - `ticket_id` is public and safe to log for request tracing and correlation.

---

## DynamoDB Shape Reference

Refer to the `submit` module and infrastructure specifications for table design:
1. Table name from environment variable `TICKETS_TABLE_NAME`.
2. Partition key: `ticket_id` (`String`).
3. TTL attribute: `expires_at` (`Number`, epoch seconds).
4. Hash attribute: `secret_hash` (`String`, SHA-256 hex digest of raw secret bytes).
5. State attribute: `job_status` (`String`, e.g. `issued`, `AWAITING_UPLOAD`, `PROCESSING`, `COMPLETE`).
6. All attributes use `snake_case`.

---

## Project Environment & Dependencies (UV)

The module is structured as `backend/check-ticket`, managed using **uv** matching `backend/submit`:

### `pyproject.toml` Specification
- **Runtime**: Python `>=3.12`
- **Package Name**: `check-ticket` (Python package `check_ticket`)
- **Dependencies**:
  - `boto3>=1.34.0`
  - `python-ulid>=4.0.1`
  - `mint-ticket` (referenced as a local editable source: `[tool.uv.sources] mint-ticket = { path = "../mint-ticket" }`)
- **CLI Scripts**:
  ```toml
  [project.scripts]
  check-ticket = "check_ticket.cli:main"
  ```
- **Dev Dependencies**:
  - `pytest>=8.0.0`
  - `pytest-cov>=5.0.0`
  - `pytest-mock>=3.14.0`
  - `ruff>=0.5.0`
- **Build Backend**: `hatchling` (`packages = ["src/check_ticket"]`)

---

## CLI Interface & Manual Testing

Mirroring `backend/submit/src/submit/cli.py`, a dedicated CLI wrapper is provided at `check_ticket.cli` 
(entrypoint: `check-ticket`) to allow testing and exercising authorization flows directly from the 
terminal without API Gateway.

### CLI Parameters
- `--table-name` *(optional string)*: DynamoDB tickets table name. Defaults to `TICKETS_TABLE_NAME` 
(or `DYNAMODB_TABLE_NAME`) environment variable. Required if environment variable is unset.
- `--auth-header` / `--authorization` *(optional string)*: The complete HTTP `Authorization` header value to validate 
(e.g. `"Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A"`).
- `--ticket-id` *(optional string)*: Ticket ULID (convenience option alternative to `--auth-header`).
- `--secret` *(optional string)*: Raw bearer secret (convenience option alternative to `--auth-header`).
- `--method-arn` *(optional string)*: Simulated API Gateway method ARN. Defaults to 
`arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status`.
- `--event` *(optional string)*: JSON string or file path containing an API Gateway authorizer event payload 
(Token authorizer or Request authorizer shape).
- **Stdin Support**: When `--auth-header`, `--event`, and `--ticket-id`/`--secret` are omitted and stdin is not a TTY, 
reads the event JSON or raw authorization header from standard input.

### CLI Behavior & Exit Codes
- **Success (Authorized)**: Prints the generated IAM policy JSON (including `principalId`, `policyDocument`, 
and `context`) to `stdout` with exit code `0`.
- **Failure (Unauthorized / Malformed)**: Prints a structured error message (`Error: Unauthorized` or specific 
parameter validation error) to `stderr` and exits with exit code `1`.

### Manual CLI Validation Steps
The following manual test steps validate authorizer functionality end-to-end against live or LocalStack DynamoDB.
Remember to set AWS_PROFILE to the appropriate profile for your environment.  If you're not using the 
correct profile you'll get the following error as you'll not find your database:
```text
An error occurred (ResourceNotFoundException) when calling the GetItem operation: Requested resource not found
```

1. **Mint a fresh test ticket:**
   ```bash
   uv run ticket-issuer --table-name pii-tickets-dev
   # Output: {"ticket_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "secret": "4yT8I1i_o23XU-Y5kS8u7A"}
   ```

2. **Validate valid ticket and secret:**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A"
   # Expected Output: JSON Allow policy with principalId "ticket:01ARZ3NDEKTSV4RRFFQ69G5FAV" and exit code 0
   ```

3. **Validate invalid secret (hash mismatch):**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:invalid_secret_value"
   # Expected Output: "Error: Unauthorized" written to stderr, exit code 1
   ```

4. **Validate non-existent ticket ID:**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FA9:4yT8I1i_o23XU-Y5kS8u7A"
   # Expected Output: "Error: Unauthorized" written to stderr, exit code 1
   ```

5. **Validate malformed authorization scheme or missing header:**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Bearer some-jwt-token"
   # Expected Output: "Error: Unauthorized" written to stderr, exit code 1
   ```

6. **Validate piped authorizer event via stdin:**
   ```bash
   echo '{"authorizationToken": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A", "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status"}' \
     | uv run check-ticket --table-name pii-tickets-dev
   # Expected Output: JSON Allow policy with wildcard stage ARN and exit code 0
   ```

---

## Packaging

Mirroring `backend/submit/build_n_package_lambda.sh`:
- ZIP deployment package containing all runtime dependencies (no container runtime in production).
- Python 3.12, arm64 Graviton2 architecture, uv for dependency management.
- Build script `backend/check-ticket/build_n_package_lambda.sh`:
  1. Clean and initialize staging directory `build_lambda/`.
  2. Execute within a `public.ecr.aws/lambda/python:3.12` Docker container (`--platform linux/arm64`):
     ```bash
     pip install --no-cache-dir uv && uv pip install --system --target /var/backend/check-ticket/build_lambda .
     ```
  3. Clean up build artifacts: remove `tests/`, `__pycache__`, `.pyc`, `.pyo`, and strip `.so` shared object binaries.
  4. Archive directory into `check_ticket.zip`.
  5. Output package metadata: package name (`check_ticket.zip`), SHA-256 digest, handler (`check_ticket.lambda_handler.handler`), runtime (`python3.12`), and target architecture (`arm64`).

---

## Documentation (`deployment.md`)

Add `backend/check-ticket/deployment.md` mirroring `backend/submit/submit_deployment.md`:
- **Overview**: Role of custom Lambda authorizer in securing REST API endpoints (`/pii-report-status`, `/pii-report`).
- **Lambda Deployment**:
  - Prerequisites (Docker, Python 3.12, uv, zip).
  - Building the Package (`build_n_package_lambda.sh`).
  - Lambda Configuration (arm64, Python 3.12, handler `check_ticket.lambda_handler.handler`, 256 MB memory, 10 s timeout, 512 MB ephemeral storage).
  - Environment Variables table (`TICKETS_TABLE_NAME`).
- **Event Contracts**: Token authorizer payload (`authorizationToken`, `methodArn`) and Request authorizer payload (`headers.Authorization`).
- **Lambda Responses**: Allow IAM policy structure with wildcard stage ARN and `context.ticketId`; failure semantics via `raise Exception("Unauthorized")` mapping to HTTP 401.
- **Testing Methodology**:
  - Unit tests with coverage reporting via uv.
  - CLI usage examples and manual validation steps.
  - Direct Python invocation snippet.
  - AWS CLI invocation example (`aws lambda invoke`).

---

## Acceptance Criteria

- **Header Parsing & Validation:**
  - Accepts credentials strictly formatted as `Authorization: Ticket <ticket_id>:<secret>`.
  - Rejects missing, empty, or malformed headers by raising `"Unauthorized"` (resulting in HTTP 401).
  - Validates that `ticket_id` conforms to a 26-character canonical ULID.
  - Rejects schemes other than `Ticket` (e.g. `Bearer`, `Basic`).

- **DynamoDB Integration:**
  - Queries `TICKETS_TABLE_NAME` by partition key `ticket_id` using an injected/mockable `boto3` DynamoDB client.
  - Rejects non-existent tickets by raising `"Unauthorized"`.
  - Reads `expires_at` and rejects tickets where current epoch time is greater than or equal to `expires_at` by raising `"Unauthorized"`.

- **Secret Verification:**
  - Decodes base64url `secret` into raw bytes, computes SHA-256 hex digest, and compares with stored `secret_hash` using constant-time comparison (`hmac.compare_digest`).
  - Utilizes shared verification logic consistent with `mint_ticket` to eliminate duplicate hashing rules.
  - Rejects invalid secrets by raising `"Unauthorized"`.

- **IAM Policy & Context Generation:**
  - On successful authorization, returns an IAM policy with `Effect: "Allow"` and `principalId: "ticket:<ticket_id>"`.
  - Scopes policy `Resource` to a wildcard stage ARN (`arn:aws:execute-api:<region>:<account>:<apiId>/<stage>/*/*`) derived from `methodArn`, allowing API Gateway caching across endpoints.
  - Injects `ticketId` into the `context` dictionary so downstream Lambdas can consume trusted session identity.

- **Separation of Responsibilities:**
  - Does not deny access based on `job_status`; leaves route-specific lifecycle enforcement to downstream Lambdas.

- **Security & Privacy:**
  - Raw secrets, authorization headers, and computed hashes are never logged to stdout or CloudWatch.
  - Logs include `ticket_id` for debugging and observability.

- **Environment & Dependency Management (UV):**
  - Project uses uv environment with `pyproject.toml` specifying Python `>=3.12`, `check-ticket` package, `mint-ticket` path source, and dev dependencies (`pytest`, `pytest-cov`, `pytest-mock`, `ruff`).
  - Defines console script entrypoint `check-ticket = "check_ticket.cli:main"`.

- **CLI Interface & Manual Testing:**
  - CLI wrapper (`check_ticket.cli` / `check-ticket`) provides parameters mirroring `submit.cli`: `--table-name` (with `TICKETS_TABLE_NAME` fallback), `--auth-header`, `--ticket-id`, `--secret`, `--method-arn`, `--event`, and stdin piping.
  - Prints IAM policy JSON to stdout and exits with code 0 on success; prints error message to stderr and exits with code 1 on authorization failure.
  - Manual test steps for CLI validation are fully documented in the user story and deployment documentation.

- **Packaging & Deployment Documentation:**
  - Packaging script `build_n_package_lambda.sh` produces reproducible arm64 ZIP package for Python 3.12 using uv in Docker.
  - `deployment.md` documentation comprehensively details prerequisites, build instructions, Lambda configuration, environment variables, event contracts, policy generation, and multi-tier testing.

- **Testability & Quality (>= 80% Coverage):**
  - Supports both Token authorizer events (`event["authorizationToken"]`) and Request authorizer events (`event["headers"]["Authorization"]`).
  - DynamoDB client is injectable for comprehensive unit testing without requiring live AWS credentials.
  - Unit tests executed via `uv run pytest --cov=check_ticket --cov-report=term-missing` achieve at least 80% code coverage across valid authorization, missing/malformed headers, ticket not found, expired tickets, secret mismatch, DynamoDB errors, and CLI interactions.

---

## Explicitly Out of Scope

- Implementing downstream business logic or job status enforcement for `GET /pii-report-status` or `GET /pii-report`.
- Terraform/CloudFormation provisioning of API Gateway routes and Lambda authorizer bindings.
- Modifying S3 presigned URL authorization or direct S3 upload policies.
- Client-side token storage and HTTP request header management in the web frontend.
