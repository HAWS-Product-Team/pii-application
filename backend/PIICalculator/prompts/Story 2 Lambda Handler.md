# Story: Create PIICalculation Lambda for Staged Pipeline

## Summary

As an application developer,  
I want the PIICalculation workload to run as an AWS Lambda function,  
so that the lightweight PIICalculation stage can execute after the classifier completes without using the expensive inference container.

## Background

The pipeline is moving to a staged architecture:
```Classifier -> PIICalculation``` 

The classifier is already containerized for AWS Batch and runs as the expensive inference workload.

PIICalculation is short-running and typically completes in seconds. It should run as Lambda rather than as an AWS Batch container.

The Lambda function should be invoked by Step Functions after the classifier Batch job succeeds.

## Target Runtime Behavior

The PIICalculation Lambda should receive an event containing S3 artifact locations:
```json 
{ "input-s3-uri": "s3://pii-data-pipeline-input/123456789/classified.csv", 
  "output-s3-uri": "s3://pii-data-pipeline-output/123456789/pii-report.json" }
``` 

The Lambda should:
```read classified CSV from S3 compute PIICalculation report write JSON report to S3 return success metadata to Step Functions``` 

## Target Pipeline Contract

## Input Artifact

The Lambda input CSV is the classifier output:
```s3://<work-bucket>/<ticket number>/classified.csv``` 

The classified CSV must contain the columns required by PIICalculation.

## Output Artifact

The Lambda output JSON report should be written to:
```s3://<output-bucket>/<ticket-id>/pii-report.json``` 

## Lambda Event Contract

The Lambda handler should accept:
```json 
{ "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/classified.csv",
  "output-s3-uri": "s3://pii-data-pipeline-output-dev/123456789/pii-report.json" }
``` 

## Lambda Response Contract

On success, the Lambda should return:
```json 
{ "ticket": "123456789", "status": "SUCCEEDED",  
  "output-s3-uri": "s3://pii-output/123456789/pii-report.json" }
``` 
Ticket number is the same as the number in the path after the bucket name.

On failure, the Lambda should raise an exception or return an error in a way that causes Step Functions to mark the `CalculatePII` state as failed.

## Application Scope

Add Lambda support to the PIICalculation application.

The implementation should include:

- A Lambda handler entrypoint.
- S3 input loading for `classified.csv`.
- S3 output writing for `pii-report.json`.
- Input event validation.
- Clear error handling for invalid events and S3 failures.
- Unit tests for the Lambda handler.
- Documentation for building/deploying the Lambda artifact.

Suggested handler shape:
```piicalculator.lambda_handler.handler``` 

Suggested project location:
```backend/PIICalculator/src/piicalculator/lambda_handler.py``` 

## Required Behavior

The Lambda handler must:

- Require `input-s3-uri`.
- Require `output-s3-uri`.
- Validate that `input-s3-uri` is an S3 URI.
- Validate that `output-s3-uri` is an S3 URI.
- Validate that the ticket number (in the path after the bucket name) is the same for input-s3-uri and output-s3-uri
- Read the classified CSV from `input-s3-uri`.
- Generate the PIICalculation JSON report.
- Write the JSON report to `output-s3-uri`.
- Return a success response after the JSON report is written.
- Raise a useful error on malformed input.
- Raise a useful error when the input CSV cannot be read.
- Raise a useful error when the output JSON cannot be written.
- Avoid logging sensitive CSV contents.
- Avoid writing the JSON report to stdout as the production Lambda output path.

## Compatibility with Existing CLI

The existing CLI behavior may remain available for local development.

For example:
```pii-calculator path/to/classified.csv path/to/output.json``` 

will work when executed locally.

The Lambda handler should be the production integration point for Step Functions.

## S3 Behavior

The Lambda must be able to:

- Parse `s3://bucket/key` URIs.
- Read the classified CSV from S3.
- Write the generated JSON report to S3.
- Surface helpful errors for:
  - malformed S3 URI
  - missing input object
  - access denied
  - invalid AWS credentials
  - missing required CSV columns
  - invalid CSV content
  - output write failure

## Packaging Approach

The PIICalculation Lambda packaged as a ZIP deployment package with dependencies.

Add build documentation or a build script that:
- Installs production dependencies into a build directory.
- Copies PIICalculation source into the build directory.
- Produces a ZIP artifact suitable for Lambda deployment.
- Uses Python 3.12.
- Uses `uv` for dependency management where practical.

## Testing Requirements

Add or update tests to verify:

- The Lambda handler accepts a valid event.
- The Lambda handler rejects an event missing `input-s3-uri`.
- The Lambda handler rejects an event missing `output-s3-uri`.
- The Lambda handler rejects malformed S3 URIs.
- The Lambda handler validates that the ticket number (in the path after the bucket name) is the same 
for input-s3-uri and output-s3-uri
- The Lambda handler reads classified CSV input from S3.
- The Lambda handler writes JSON output to S3.
- The Lambda handler returns the expected success response.
- The Lambda handler raises an error when the input CSV is invalid.
- The Lambda handler raises an error when required CSV columns are missing.
- The Lambda handler raises an error when the output JSON cannot be written.
- Existing PIICalculation CLI tests continue to pass.

S3 interactions should be mocked or faked in unit tests.

## Manual Validation

A developer should be able to run the Lambda handler locally with a representative event.

Example event:
```json 
{ "input-s3-uri": "s3://pii-data-pipeline-input/1234/classified.csv", "output-s3-uri": "s3://pii-data-pipeline-input/1234/pii-report.json" }
``` 

## Acceptance Criteria

- A PIICalculation Lambda handler exists.
- The handler accepts `input-s3-uri`, and `output-s3-uri`.
- The handler validates required event fields.
- The handler validates S3 URI format for input and output.
- The handler reads the classified CSV from S3.
- The handler computes the PIICalculation report.
- The handler writes the JSON report to the specified S3 output URI.
- The handler returns a success response containing:
  - `ticket`
  - `status`
  - `output-s3-uri`
- The handler raises an error for invalid input events.
- The handler raises an error for missing or unreadable input CSV.
- The handler raises an error for invalid CSV contents.
- The handler raises an error when output JSON cannot be written.
- The handler does not log raw CSV contents.
- The handler does not require the classifier inference container.
- The PIICalculation Lambda package uses Python 3.12.
- Production dependencies are installable reproducibly.
- Existing PIICalculation tests pass.
- New tests cover the Lambda handler behavior.
- S3 interactions are mocked or faked in unit tests.
- Documentation is added or updated with Lambda packaging and local validation instructions.

## Out of Scope

- Creating or modifying the classifier ECR container image.
- Modifying AWS Batch infrastructure for the classifier.
- Creating Step Functions infrastructure.
- Creating normalizer or anonymizer stages.
- Frontend integration.
- API changes for starting pipeline executions.
- Performance optimization of the PIICalculation algorithm.
- Moving PIICalculation to AWS Batch.

## Notes

This story should be implemented in the application repository.

The infrastructure repository should consume the Lambda handler package or Lambda container image produced by this story.