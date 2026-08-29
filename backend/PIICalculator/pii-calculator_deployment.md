# PII Calculator Deployment

This document describes how to deploy and integrate the PII Calculator in AWS Lambda and AWS Step Functions.

## Overview

The PIICalculator is designed to run as a lightweight Lambda function in the staged pipeline. It replaces the need for 
an inference container for the calculation stage and executes after the data classification stage completes.

---

## Lambda Deployment

### Prerequisites

- Docker
- Python 3.12
- [uv](https://github.com/astral-sh/uv) for dependency management
- `zip` utility

### Building the Package

To produce a deployment artifact, run the provided build script:

```bash
./build_n_package_lambda.sh
```

This script will:
1. Create a `build_lambda` directory.
2. Install production dependencies and the `piicalculator` package into it.
3. Clean up unnecessary files (like `__pycache__`).
4. Produce `pii-calculator-lambda.zip`.

### Lambda Configuration

To reduce costs, the Lambda should be configured to run on the `arm64` architecture.

#### Lambda Settings

- **Architectures**: arm64
- **Runtime**: Python 3.12
- **Handler**: `piicalculator.lambda_handler.handler`
- **Memory**: 512 MB (recommended)
- **Timeout**: 60 seconds (should typically complete in < 10s)

#### Environment Variables

- `MAXCSVFILESIZE`: (Optional) Maximum allowed size for the input CSV in MB. Defaults to 20.

### Event Contract

The Lambda expects an event with S3 URI locations for the input classified CSV and the output PII report.

**Example Event:**
```json
{
  "ticket": "123456789",
  "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/classified.csv",
  "output-s3-uri": "s3://pii-data-pipeline-output-dev/123456789/pii-report.json"
}
```

**Validation Rules:**
- Both URIs must be valid S3 URIs starting with `s3://`.
- The ticket number (the first part of the S3 key) must match between input and output URIs.

### Lambda Success Response

On success, the Lambda returns:

```json
{
  "ticket": "123456789",
  "status": "SUCCEEDED",
  "output-s3-uri": "s3://pii-data-pipeline-output-dev/123456789/pii-report.json"
}
```

### Direct Lambda Testing

You can test the handler locally using a test script or invoke the function directly via AWS CLI.

**Local Python Test:**
```python
from piicalculator.lambda_handler import handler

event = {
    "ticket": "1234",
    "input-s3-uri": "s3://your-bucket/1234/classified.csv",
    "output-s3-uri": "s3://your-bucket/1234/pii-report.json"
}
# Note: Requires AWS credentials and access to the S3 paths
handler(event, None)
```

**AWS CLI Lambda Invoke:**
```bash
aws lambda invoke \
  --function-name pii-calculator \
  --payload '{"ticket":"123456789","input-s3-uri":"s3://pii-data-pipeline-input-dev/123456789/classified.csv","output-s3-uri":"s3://pii-data-pipeline-output-dev/123456789/pii-report.json"}' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

---

## Step Functions

### Integration Overview

In the data pipeline architecture, AWS Step Functions acts as the orchestrator. After the upstream classification
stage completes and writes `classified.csv` to S3, Step Functions triggers the PII Calculator Lambda stage 
(e.g., `CalculatePII` task) by passing the input and output S3 URI parameters.

### Testing by Triggering Step Functions

You can test the Step Functions execution end-to-end to verify that the state machine invokes the PII Calculator 
Lambda and successfully generates the PII report.  By examining the terraform plan for the state machine, look at the
parameters needed by the various tasks.  Each unique parameter will need to be passed to the state machine via a 
message.  

Here is an example message that can be used to trigger the state machine:

```json
{
  "ticket": "123456789",
   "inputCsv": "s3://pii-data-pipeline-input-dev/123456789/purchase_data.csv",
  "classifiedCsv": "s3://pii-data-pipeline-input-dev/123456789/classified.csv", 
  "piiReportJson": "s3://pii-data-pipeline-output-dev/123456789/pii-report.json"
}
```

#### 1. Prepare Test Data in S3

Ensure that a valid `classified.csv` exists in the input S3 bucket:

```bash
aws s3 cp classified.csv s3://pii-data-pipeline-input-dev/123456789/classified.csv
```

#### 2. Trigger via AWS CLI

Trigger the state machine execution using the `aws stepfunctions start-execution` command:

```bash
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:<region>:<account-id>:stateMachine:<state-machine-name>" \
  --name "test-pii-calc-$(date +%s)" \
  --input '{
    "ticket": "123456789",
    "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/classified.csv",
    "output-s3-uri": "s3://pii-data-pipeline-output-dev/123456789/pii-report.json"
  }'
```

To check the execution status:

```bash
aws stepfunctions describe-execution \
  --execution-arn "<execution-arn-from-previous-command>"
```

#### 3. Trigger via AWS Management Console

1. Navigate to the **AWS Step Functions** console.
2. Select your pipeline state machine from the list.
3. Click **Start execution**.
4. (Optional) Provide an execution name.
5. In the **Input** JSON editor, enter the test payload:
   ```json
   {
     "ticket": "123456789",
     "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/classified.csv",
     "output-s3-uri": "s3://pii-data-pipeline-output-dev/123456789/pii-report.json"
   }
   ```
6. Click **Start execution**.
7. In the execution visual graph, verify that the `CalculatePII` state turns green (`Succeeded`).

#### 4. Verify Output Artifact

Confirm that the output JSON report has been generated in S3:

```bash
aws s3 cp s3://pii-data-pipeline-output-dev/123456789/pii-report.json ./pii-report.json
cat ./pii-report.json
```
