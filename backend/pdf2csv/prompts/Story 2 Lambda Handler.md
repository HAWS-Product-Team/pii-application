# Story: Create pdf2csv Lambda for Staged Pipeline

## Summary

As an application developer,  
I want the pdf2csv workload to run as an AWS Lambda function,  
so that the lightweight pdf2csv stage can execute after the user has uploaded their data in pdf format, and do this
without a heavyweight, slower starting container.  

## Background

The pipeline has moved to a staged architecture:
```pdf2csv -> Classifier -> PIICalculation``` 

The classifier is already containerized for AWS Batch and runs as the expensive inference workload.

PIICalculation is short-running and typically completes in seconds. It should run as Lambda rather than as an AWS Batch container.

Now create the lambda for pdf2csv. The Lambda function should be invoked by Step Functions, notified to get started by
an event detailing the S3 artifact locations of the input and output paths (directories) and the ticket number.

## Target Runtime Behavior

The pdf2csv Lambda should receive an event containing S3 artifact locations.  Since pdf2csv will process by converting 
the contents of the entire path from pdfs to csvs, we just want paths rather than files. 
```json 
{ "input-s3-uri": "s3://pii-data-pipeline-input/123456789/upload/"}
``` 

The Lambda should:convert each file at the input-s3-uri into a csv.  It will 
name the file to the same name as the input file but with a .csv extension.

## Input Artifact

The Lambda input is the location of where the data was uploaded by the user:
```s3://<work-bucket>/<ticket number>/upload``` 

The CSV must contain the columns required by PIICalculation.

## Output Artifact

The Lambda outputs csv files should be written to the same location from whence they were loaded:
```s3://<output-bucket>/<ticket-id>/upload``` 

## Lambda Event Contract

The Lambda handler should accept:
```json 
{ "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
``` 

## Lambda Response Contract

On success, the Lambda should return:
```json 
{ "ticket": "123456789", "status": "SUCCEEDED",  
  "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload" }
```
Ticket number is the same as the number in the path after the bucket name.

On failure, the Lambda should raise an exception or return an error in a way that causes Step Functions to mark the `pdf2csv` state as failed.

## Application Scope

Add Lambda support to the pdf2csv application.

The implementation should include:

- A Lambda handler entrypoint.
- S3 input with a path that directs where to process files.
- Input event validation.
- Clear error handling for invalid events and S3 failures.
- Unit tests for the Lambda handler.
- Documentation for building/deploying the Lambda artifact similar to: ```./backend/PIICalculator/pii-calculator_deployment.md```
- A shell script to build and package the lambda artifac similar to: ```./backend/PIICalculator/build_n_package_lamda.sh```

Suggested handler shape:
```pd2csv.lambda_handler.handler``` 

Suggested project location:
```backend/pdf2csv/src/pdf2csv/lambda_handler.py``` 

## Required Behavior

The Lambda handler must:

- Require `input-s3-uri`.
- Validate that `input-s3-uri` is an S3 URI.
- Read the pdfs from `input-s3-uri`.
- Generate the csvs from the pdfs at the same location and same filename but with a .csv extension.
- Return a success response after csvs are written.
- Raise a useful error on malformed input.
- Raise a useful error when an input pdfs cannot be read.
- Raise a useful error when the output csvs cannot be written.
- Avoid logging sensitive pdf contents.
- Avoid writing the csv to stdout.

## Compatibility with Existing CLI

The existing CLI behavior may remain available for local development.

For example:
```pdf2csv path/to/read_from path/to/write_to``` 

will work when executed locally.

The Lambda handler should be the production integration point for Step Functions.  The handler will simply 
use the same input uri as the output uri when communicating with the python app.

## S3 Behavior

The Lambda must be able to:

- Parse `s3://bucket/key` URIs.
- Read the classified pdf from S3.
- Write the generated csv report to S3.
- Surface helpful errors for:
  - malformed S3 URI
  - missing input path
  - missing ticket number after the bucket name
  - access denied
  - invalid AWS credentials
  - no pdfs are at the input path
  - invalid CSV content
  - write failure

## Packaging Approach

The pdf2csv Lambda packaged as a ZIP deployment package with dependencies.

Add build documentation or a build script that:
- Installs production dependencies into a build directory.
- Copies pdf2csv source into the build directory.
- Produces a ZIP artifact suitable for Lambda deployment.
- Uses Python 3.12.
- Uses `uv` for dependency management where practical.

## Testing Requirements

Add or update tests to verify:

- The Lambda handler accepts a valid event.
- The Lambda handler rejects an event missing `input-s3-uri`.
- The Lambda handler rejects malformed S3 URIs.
- The Lambda handler validates that there is a ticket number (in the path after the bucket name) 
for input-s3-uri
- The Lambda handler reads pdf input from S3.
- The Lambda handler writes csv output to S3.
- The Lambda handler returns the expected success response.
- The Lambda handler raises an error when there are no pdfs at the input-s3-uri.
- The Lambda handler raises an error when the output csv cannot be written.
- Existing pdf2csv CLI tests continue to pass.

S3 interactions should be mocked or faked in unit tests.

## Manual Validation

A developer should be able to run the Lambda handler locally with a representative event.

Example event:
```json 
{ "input-s3-uri": "s3://pii-data-pipeline-input/1234/upload" }
``` 

## Acceptance Criteria

- A pdf2csv Lambda handler exists.
- The handler accepts `input-s3-uri`.
- The handler validates pdf files exist at `input-s3-uri`.
- The handler validates S3 URI format for input and that there is a ticket number after the bucket name.
- The handler reads the pdfs from S3.
- The handler writes the csv to the specified S3 output URI.
- The handler returns a success response containing:
  - `ticket`
  - `status`
  - `output-s3-uri`
- The handler raises an error for invalid input events.
- The handler raises an error for missing or unreadable input pdfs.
- The handler raises an error when output csv cannot be written.
- The handler does not log raw CSV or pdf contents.
- The handler does not require running in a container.
- The pdf2csv Lambda package uses Python 3.12.
- Production dependencies are installable reproducibly.
- Existing pdf2csv tests pass.
- New tests cover the Lambda handler behavior.
- S3 interactions are mocked or faked in unit tests.
- Documentation is added or updated with Lambda packaging and local validation instructions.

## Out of Scope

- Creating Step Functions infrastructure.
- Frontend integration.
- API changes for starting pipeline executions.

## Notes

This story should be implemented in the application repository.

The infrastructure repository should consume the Lambda handler package or Lambda container image produced by this story.