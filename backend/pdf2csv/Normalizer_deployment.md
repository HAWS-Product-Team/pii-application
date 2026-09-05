# Normalizer Lambda Deployment & Local Validation

## Overview

The **Normalizer** Lambda function is the first processing stage in the PII Data Pipeline:

```
User Upload (PDF) ──► Normalizer (Lambda) ──► Classifier (AWS Batch) ──► PIICalculation (Lambda)
```

The Normalizer takes user-uploaded spending-statement PDFs in S3, parses transaction records, and converts them to standardized CSVs in place within the same S3 prefix (`.pdf` replaced by `.csv`). This allows lightweight, fast execution directly upon upload without spinning up heavyweight container tasks.

---

## Lambda Deployment

### Prerequisites

- **Docker**: For reproducible arm64 Linux builds via official AWS Lambda base images
- **Python 3.12**: Runtime version
- **uv**: Fast Python packaging and dependency resolver
- **zip**: Packaging utility

### Building the Package

Run the packaging script from `backend/pdf2csv`:

```bash
chmod +x build_n_package_lambda.sh
./build_n_package_lambda.sh
```

This script:
1. Cleans the `build_lambda/` staging directory.
2. Runs a `public.ecr.aws/lambda/python:3.12` Docker container under `--platform linux/arm64`.
3. Installs dependencies using `uv pip install --target build_lambda .`.
4. Removes unnecessary artifacts (`tests/`, `__pycache__`, `.pyc`, etc.) and strips `.so` binaries.
5. Archives the build directory into `Normalizer-lambda.zip` and outputs the package SHA-256 digest.

### Lambda Configuration

| Parameter | Value | Notes |
|---|---|---|
| **Runtime** | `python3.12` | Python 3.12 |
| **Architecture** | `arm64` | AWS Graviton2 / Linux |
| **Handler** | `pdf2csv.lambda_handler.handler` | Module entrypoint |
| **Memory** | `1536 MB` | 1.5 GB |
| **Timeout** | `180 seconds` | 3 minutes |
| **Ephemeral Storage (/tmp)** | `5120 MB` | 5 GB (handler guards 80% / 4 GB budget) |
| **Environment Variables** | None currently required | S3 credentials/region resolved via IAM role |

### Event Contract

The Lambda receives an event containing the S3 URI where the PDFs are located:

```json
{
  "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"
}
```

- `input-s3-uri` *(required, string)*: Valid `s3://bucket/key` URI.
- The first path segment after the bucket name must be the numeric ticket number (e.g., `123456789`).
- Trailing slashes are optional (e.g., `s3://bucket/123456789/uploads/`).

### Lambda Success Response

On successful processing, the handler returns:

```json
{
  "ticket": "123456789",
  "status": "SUCCEEDED",
  "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"
}
```
# Testing
I've been using the following testing method which follows the principle of testing the simplist portion, then build 
on top of that known good piece and testing more on top of that, continuing that process until it's all testing and 
working.  That process instills the knowledge of how things are working seperately and in concert.

Testing:
- unit tests for the python program pass
- local python invocation passes for local files
- local python invocation passes for files on s3
- deployed lambda invocation passes on s3
- deployed step function passes

Following this method, when a problem surfaces, there is less "depth" to investigate for the root cause.
In this document we'll talk about the last two: lambda and step function

## Direct Lambda Testing
### Deploy lambda
The infrastructure code will look for the `normalizer.zip` file in `s3://pii-data-pipeline-input-dev/lambdas/`.
`aws s3 cp normalizer.zip s3://pii-data-pipeline-input-dev/lambdas/`

Then run terraform plan which will deploy the new .zip

### AWS CLI Invocation
Put test .pdfs into the upload location and then do the below.

```bash
aws lambda invoke \
  --function-name pii-normalizer-dev \
  --payload '{"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
```
or if having difficulty with payload on the command line, put it into a json file.
```bash
AWS_PAGINATOR=off aws lambda invoke \
  --function-name pii-normalizer-dev \
  --payload file://payload.json \
  --cli-binary-format raw-in-base64-out \
  response.json
{
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
}

 cat response.json  
 {"ticket": "123456789", "status": "SUCCEEDED", "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/uploads"}
```

## Step Function Invocation
Since step function interface incorporates all of the lambdas, those instructions are located [with pii-calculator documentation](../PIICalculator/pii-calculator_deployment.md).
See the section on Step Functions.
---

## Local Validation with LocalStack

You can test the entire workflow locally using LocalStack:

### 1. Start LocalStack

```bash
docker run --rm -d \
  --name localstack-normalizer \
  -p 4566:4566 \
  -e SERVICES=s3 \
  localstack/localstack:latest
```

### 2. Create Bucket and Upload Sample PDF

```bash
# Create bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://pii-data-pipeline-input-dev

# Upload sample PDF statement
aws --endpoint-url=http://localhost:4566 s3 cp \
  data/AmazonOrderHistoryPDFs/1.pdf \
  s3://pii-data-pipeline-input-dev/123456789/uploads/1.pdf
```

### 3. Run Handler against LocalStack

```python
import boto3
from pdf2csv.lambda_handler import handler

# Configure S3 client pointing to LocalStack
s3_client = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1",
)

event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/uploads"}

response = handler(event, s3_client=s3_client)
print("Handler Response:", response)
```

### 4. Verify Output CSV in S3

```bash
aws --endpoint-url=http://localhost:4566 s3 ls s3://pii-data-pipeline-input-dev/123456789/uploads/

# Download and inspect CSV
aws --endpoint-url=http://localhost:4566 s3 cp \
  s3://pii-data-pipeline-input-dev/123456789/uploads/1.csv -
```

---

## Step Functions Integration

The Normalizer Step Functions state machine is defined and managed in the infrastructure repository.

### State Machine Payload

Step Functions passes the input S3 URI to the Normalizer task:

```json
{
  "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/uploads"
}
```

### Triggering Execution

Once wired via Terraform, an execution can be triggered via AWS CLI:

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:PIIDataPipeline \
  --input '{"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/uploads"}'
```

# Troubleshooting
## Problem: lambda response is: `"errorMessage": "'module' object is not callable"`
This happens when calling the function:
```bash
$ AWS_PAGINATOR=off aws lambda invoke \
  --function-name pii-normalizer-dev \
  --payload file://payload.json \
  --cli-binary-format raw-in-base64-out \
  response.json
{
    "StatusCode": 200,
    "FunctionError": "Unhandled",
    "ExecutedVersion": "$LATEST"
}

cat response.json  
{"errorMessage": "'module' object is not callable", "errorType": "TypeError", "requestId": "5cd501c5-3dbf-45ca-8afe-08da9f9b0a34", "stackTrace": ["  File \"/var/lang/lib/python3.12/site-packages/awslambdaric/bootstrap.py\", line 178, in handle_event_request\n    response = request_handler(event, lambda_context)\n"]}%
```    
### Solution: Agentic AI has been reference the python module instead of the function. Change the terraform plan to
reference the function.
```terraform
resource "aws_lambda_function" "normalizer" {
  ...
  handler =....
}
```

## Problem: When calling the Invoke operation: Function not found: ... Normalizer:$LATEST
The above error happens when using `aws lambda invoke --function-name ... --payload .... --cli-binary-format raw-in-base64-out ...`.
### Solution: 
Double check that the function name is correct. Typically `pii-normalizer-dev`