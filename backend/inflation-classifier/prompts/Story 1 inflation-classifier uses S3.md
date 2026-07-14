# inflation-classifier supports S3 input paths

## User Story

As a user of `inflation-classifier`,
I want to provide either a local file path or an S3 URI as the input argument,
so that I can classify files stored locally or in Amazon S3 without manually downloading them first.

## Background

The classifier currently accepts local filesystem paths, for example:

This story adds support for S3 URIs using the `s3://bucket/key` format, for example:

Local file behavior must continue to work exactly as it does today.

## Scope

Add support for input paths beginning with `s3://`.

The classifier should:

- Detect when the provided input argument is an S3 URI.
- Read the referenced S3 object.
- Decode the S3 object content as text using the same encoding behavior as local file input.
- Pass the file contents into the existing classification flow.
- Print classification results to `stdout`, consistent with local-file input behavior.
- Preserve existing local filesystem input behavior.

## Out of Scope

The following are not required for this story:

- Writing classification results back to S3.
- Supporting S3 prefixes/directories.
- Supporting wildcard S3 paths.
- Supporting HTTPS-style S3 URLs.
- Adding an interactive credential prompt.
- Changing the classifier output format.

## Authentication

The implementation should rely on the standard AWS credential resolution chain, such as:

- Environment variables
- AWS shared credentials/config files
- IAM role credentials when running in AWS

The application should not require credentials to be passed as command-line arguments.

## Error Handling

The classifier should fail gracefully with a clear error message when:

- The S3 URI is malformed.
- The S3 bucket does not exist.
- The S3 object does not exist.
- The caller does not have permission to read the object.
- AWS credentials are missing or invalid.
- The S3 object cannot be read.

Error messages should be written to `stderr`, and the process should exit with a non-zero status code.

## Dependency Management

If a new dependency is required for S3 access, it must be added using `uv`.

For example:
```bash 
uv add <aws-s3-library>
```
No other package manager should be used.

## Acceptance Criteria

1. Given a valid local file path,
   when the user runs:

   ```bash
   uv run inflation-classifier.py file.txt
   ```

   then the classifier reads the local file and prints classification results to `stdout`.

2. Given a valid S3 URI in the form:

   ```bash
   s3://<bucket-name>/<path-to-test-file>.csv
   ```

   when the user runs:

   ```bash
   uv run inflation-classifier.py s3://<bucket-name>/<path-to-test-file>.csv
   ```

   then the classifier reads the S3 object and prints classification results to `stdout`.

3. Given a malformed S3 URI, such as:

   ```bash
   s3://
   ```

   when the user runs the classifier,
   then the command exits with a non-zero status code and prints a helpful error message to `stderr`.

4. Given an S3 URI for an object that does not exist,
   when the user runs the classifier,
   then the command exits with a non-zero status code and prints a helpful error message to `stderr`.

5. Existing tests for local file input continue to pass.

6. New automated tests are added for:
   - S3 URI detection.
   - S3 URI parsing.
   - Successful S3 object reading, using a mocked S3 client.
   - S3 read failure behavior, using a mocked S3 client.
   - Preservation of existing local file behavior.

7. Use the following files for testing:
   - backend/tests/data/small\ test\ set/synthetic_purchases_2024_evaluation_data.csv
   -  s3://pii-data-pipeline-input-dev/123456789/synthetic_purchases_2024_evaluation_data.csv

## Manual Validation Fixture

For manual validation in the development environment, the following test fixture may be used if the developer has appropriate AWS access:
```uv run inflation-classifier.py s3://<test-bucket>/<test-account-or-prefix>/<test-file>.csv```

## Agent Implementation Notes

An AI coding agent should:

- Inspect the existing command-line entry point.
- Identify where the input file is currently opened.
- Add a small abstraction for reading input from either:
  - local filesystem path
  - S3 URI
- Keep classification logic unchanged where possible.
- Prefer unit tests with mocked S3 access rather than tests that depend on real cloud infrastructure.
- Avoid hard-coding bucket names, credentials, regions, or local absolute paths.
- Ensure errors are user-friendly and do not expose credentials or sensitive configuration.