# PII Calculator Lambda Deployment

This document describes how to build and deploy the PIICalculator as an AWS Lambda function.

## Overview

The PIICalculator is designed to run as a lightweight Lambda function in the staged pipeline. It replaces the need for an inference container for the calculation stage.

## Prerequisites

- docker
- Python 3.12
- [uv](https://github.com/astral-sh/uv) for dependency management
- `zip` utility

## Building the Package

To produce a deployment artifact, run the provided build script:

```bash
./build_n_package_lambda.sh
```

This script will:
1. Create a `build_lambda` directory.
2. Install production dependencies and the `piicalculator` package into it.
3. Clean up unnecessary files (like `__pycache__`).
4. Produce `pii-calculator-lambda.zip`.

## Configuration

### Lambda Settings

- **Runtime**: Python 3.12
- **Handler**: `piicalculator.lambda_handler.handler`
- **Memory**: 512 MB (recommended)
- **Timeout**: 60 seconds (should typically complete in < 10s)

### Environment Variables

- `MAXCSVFILESIZE`: (Optional) Maximum allowed size for the input CSV in MB. Defaults to 20.

## Event Contract

The Lambda expects an event with S3 URI locations for the input classified CSV and the output PII report.

**Example Event:**
```json
{
  "input-s3-uri": "s3://pii-data-pipeline-input/123456789/classified.csv",
  "output-s3-uri": "s3://pii-data-pipeline-output/123456789/pii-report.json"
}
```

**Validation Rules:**
- Both URIs must be valid S3 URIs starting with `s3://`.
- The ticket number (the first part of the S3 key) must match between input and output URIs.

## Success Response

On success, the Lambda returns:

```json
{
  "ticket": "123456789",
  "status": "SUCCEEDED",
  "output-s3-uri": "s3://pii-data-pipeline-output/123456789/pii-report.json"
}
```

## Local Validation

You can test the handler locally using a test script or by invoking the function in a local Lambda-like environment.

**Example Local Test:**
```python
from piicalculator.lambda_handler import handler

event = {
    "input-s3-uri": "s3://your-bucket/1234/classified.csv",
    "output-s3-uri": "s3://your-bucket/1234/pii-report.json"
}
# Note: Requires AWS credentials and access to the S3 paths
handler(event, None)
```
