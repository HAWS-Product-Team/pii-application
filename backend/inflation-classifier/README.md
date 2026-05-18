# inflation-classifier

CLI tool that classifies purchase item descriptions into inflation categories.

## Dependencies

This project uses Hugging Face Transformers for zero-shot classification.

Key packages:
- `transformers` — model/pipeline APIs
- `torch` — default backend runtime
- `datasets` — optional data tooling
- `accelerate` — device/runtime support
- `boto3` — S3 access for `s3://` input paths

Install and sync from this directory:
1. `uv sync`

## PyTorch and GPUs

### Mac (Apple Silicon)

PyTorch will typically use MPS automatically when available.

### Linux (NVIDIA)

Use a CUDA-compatible PyTorch build if needed:
`uv add torch --index-url https://download.pytorch.org/whl/cu121`

Adjust `cu121` to match your CUDA version.

## CLI usage

From `backend/inflation-classifier`:
1. `uv sync`
2. `uv run inflation-classifier [--help] [--list-wrong] <path-to-csv-or-s3-uri>`

Supported input values:
- Local file path, for example:
  - `../tests/data/small\ test\ set/synthetic_purchases_2024_evaluation_data.csv`
- S3 URI in `s3://bucket/key` format, for example:
  - `s3://pii-data-pipeline-input-dev/123456789/synthetic_purchases_2024_evaluation_data.csv`

Examples:
- Local:
  - `uv run inflation-classifier ../tests/data/small\ test\ set/synthetic_purchases_2024_evaluation_data.csv`
- S3:
  - `uv run inflation-classifier s3://pii-data-pipeline-input-dev/123456789/synthetic_purchases_2024_evaluation_data.csv`

## Docker usage

`docker run --rm -e AWS_PROFILE=pii-infrastructure -v "$HOME/.aws:/root/.aws:ro" inflation-classifier:latest s3://pii-data-pipeline-input-dev/123456789/synthetic_purchases_2024_evaluation_data.csv`

## S3 input behavior

The CLI now supports both local paths and S3 URIs as the single input argument.

When an input starts with `s3://`, the classifier will:
- parse bucket and key
- read the S3 object
- load the CSV using the same pandas behavior used for local files
- run the existing classification flow unchanged
- print results to `stdout` in the same format as local input

Error cases are surfaced as clear `stderr` messages with a non-zero exit code, including:
- malformed S3 URI
- missing bucket or object
- access denied
- missing or invalid AWS credentials

## Troubleshooting

### `AccessDenied` / permission denied when reading S3

If your `AWS_PROFILE` is not set to a profile in our AWS account, you may get permission denied errors when reading S3 objects.

Set your profile before running the CLI:

```bash
AWS_PROFILE=<our-account-profile> uv run inflation-classifier s3://<bucket>/<key>.csv
```

Also verify that:
- the selected IAM user/role has `s3:GetObject` access to the target object
- the bucket policy allows access for that principal
- your credentials are valid and not expired

# XXX WIP
- change the path in the dockerfile from "inference" to "classifier."
- read up on whether or not containers running as a root user is a concern.
- 