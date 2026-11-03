# Check Ticket Lambda Authorizer Deployment & Local Validation

## Overview

The **Check Ticket** Lambda function is the **API Gateway custom authorizer** for the PII Data Pipeline REST API:

```
Client (Browser / CLI)
  │
  ├─► Authorization: Ticket <ticket_id>:<secret>
  │
  ▼
API Gateway REST API
  │
  ├─► Check Ticket Authorizer (Lambda) ──► Validates against DynamoDB (TICKETS_TABLE_NAME)
  │                                    ──► Returns IAM Policy (Allow with wildcard stage ARN)
  ▼
Protected Endpoints (/pii-report-status, /pii-report)
```

Check Ticket intercepts incoming calls to protected REST API endpoints, validates the caller's credentials against DynamoDB, checks ticket expiration, verifies the secret hash using constant-time comparison, and generates an IAM policy granting or denying access.

---

## Lambda Deployment

### Prerequisites

- **Docker**: For reproducible arm64 Linux builds via official AWS Lambda base images
- **Python 3.12**: Runtime version
- **uv**: Fast Python packaging and dependency resolver
- **zip**: Packaging utility

### Building the Package

Run the packaging script from `backend/check-ticket`:

```bash
chmod +x build_n_package_lambda.sh
./build_n_package_lambda.sh
```

This script:
1. Cleans the `build_lambda/` staging directory.
2. Runs a `public.ecr.aws/lambda/python:3.12` Docker container under `--platform linux/arm64`.
3. Installs dependencies using `uv pip install --system --target build_lambda .`.
4. Removes unnecessary build artifacts (`tests/`, `__pycache__`, `.pyc`, etc.) and strips `.so` binaries.
5. Archives the build directory into `check_ticket.zip` and outputs the package SHA-256 digest.

### Lambda Configuration

| Parameter | Value | Notes |
|---|---|---|
| **Runtime** | `python3.12` | Python 3.12 |
| **Architecture** | `arm64` | AWS Graviton2 / Linux |
| **Handler** | `check_ticket.lambda_handler.handler` | Module entrypoint |
| **Memory** | `256 MB` | Fast execution with minimal memory footprint |
| **Timeout** | `10 seconds` | Tight SLA for API Gateway authorizers |
| **Ephemeral Storage (/tmp)** | `512 MB` | Default |

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TICKETS_TABLE_NAME` | Yes | - | DynamoDB table name storing tickets (e.g. `pii-tickets-dev`) |
| `LOG_LEVEL` | No | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Event Contracts

The handler supports both API Gateway Token authorizer and Request authorizer event shapes.

### Token Authorizer Event

```json
{
  "type": "TOKEN",
  "authorizationToken": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A",
  "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status"
}
```

### Request Authorizer Event

```json
{
  "type": "REQUEST",
  "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status",
  "headers": {
    "Authorization": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A"
  }
}
```

---

## Authorization Responses & Failure Semantics

### Authorized Response (Allow Policy)

On valid credentials, the Lambda returns an IAM policy granting invocation across the stage:

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

- **Policy Resource Scoping**: Scoped to a wildcard stage ARN (`.../<stage>/*/*`) derived from `methodArn`, allowing API Gateway to cache the authorizer decision across multiple endpoints without false denials.
- **Context Injection**: `context.ticketId` is forwarded to downstream Lambdas in `event.requestContext.authorizer.ticketId`.

### Failure Semantics (HTTP 401 Unauthorized)

For any failure (missing header, malformed header, ticket not found, expired ticket, secret mismatch, or DynamoDB exception), the Lambda raises:

```python
raise Exception("Unauthorized")
```

In AWS API Gateway, this exception instructs API Gateway to respond with `HTTP 401 Unauthorized`.

---

## Testing & Validation

Testing follows a layered progression from automated unit tests to local CLI execution and AWS deployment validation.

### 1. Unit Tests & Code Coverage

Run tests and check coverage using `uv`:

```bash
cd backend/check-ticket
uv run pytest --cov=check_ticket --cov-report=term-missing
```

### 2. Manual CLI Validation Steps

The CLI tool (`check-ticket`) allows exercising authorization directly against DynamoDB:

1. **Mint a fresh test ticket:**
   ```bash
   uv run ticket-issuer --table-name pii-tickets-dev
   # Output: {"ticket_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "secret": "4yT8I1i_o23XU-Y5kS8u7A"}
   ```

2. **Validate valid ticket and secret:**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A"
   # Exit code: 0, prints Allow policy JSON to stdout
   ```

3. **Validate invalid secret (hash mismatch):**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:invalid_secret_value"
   # Exit code: 1, prints "Error: Unauthorized" to stderr
   ```

4. **Validate non-existent ticket ID:**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FA9:4yT8I1i_o23XU-Y5kS8u7A"
   # Exit code: 1, prints "Error: Unauthorized" to stderr
   ```

5. **Validate malformed authorization scheme:**
   ```bash
   uv run check-ticket --table-name pii-tickets-dev --auth-header "Bearer some-jwt-token"
   # Exit code: 1, prints "Error: Unauthorized" to stderr
   ```

6. **Validate piped authorizer event via stdin:**
   ```bash
   echo '{"authorizationToken": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A", "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status"}' \
     | uv run check-ticket --table-name pii-tickets-dev
   # Exit code: 0, prints Allow policy JSON to stdout
   ```

### 3. Direct Python Invocation

```python
import os
from check_ticket.lambda_handler import handler

os.environ["TICKETS_TABLE_NAME"] = "pii-tickets-dev"

event = {
    "type": "TOKEN",
    "authorizationToken": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A",
    "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status",
}

policy = handler(event)
print("Policy:", policy)
```

### 4. AWS CLI Invocation

To invoke the deployed Lambda directly via AWS CLI:

```bash
aws lambda invoke \
  --function-name pii-check-ticket-dev \
  --payload '{"authorizationToken": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:4yT8I1i_o23XU-Y5kS8u7A", "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
```
