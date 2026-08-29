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

PyTorch will typically use MPS (Metal) automatically when available.

### Linux (NVIDIA)

Use a CUDA-compatible PyTorch build if needed:
`uv add torch --index-url https://download.pytorch.org/whl/cu121`

Adjust `cu121` to match your CUDA version.

## CLI usage
Use the CLI to see the extended help and usage information.
```bash
uv sync
uv run inflation-classifier -h
```

`inflation-classifier` is a tool that categorizes spending data into 8 Consumer Price Index (CPI) categories:
- Housing
- Food and Beverages
- Transportation
- Medical Care
- Energy
- Household Furnishings and Operations
- Apparel
- Recreation Education and Communication

The tool processes a CSV file, using the `item_description` column for classification. It requires two positional arguments: an input CSV path and an output CSV path. The classified CSV data (original data plus the new 'category' column) is written to the output file.

From `backend/inflation-classifier`:
1. `uv sync`
2. `uv run inflation-classifier [--help] [--evaluate] [--list-wrong] <input-csv-path> <output-csv-path>`

Supported input values:
- Local file path, for example:
  - `../tests/data/small\ test\ set/synthetic_purchases_2024_evaluation_data.csv`
- S3 URI in `s3://bucket/key` format, for example:
  - `s3://pii-data-pipeline-input-dev/123456789/synthetic_purchases_2024_evaluation_data.csv`

Examples:
Set environment variable `INFERENCE_DEVICE=mps` to use Metal.

- Local:
  - `uv run inflation-classifier input.csv output.csv`
- S3:
  - `uv run inflation-classifier s3://bucket/input.csv s3://bucket/output.csv`
  - `INFERENCE_DEVICE=mps uv run inflation-classifier s3://bucket/input.csv s3://bucket/output.csv`

## Docker usage
You can run the container locally for testing.

`docker run --rm -e AWS_PROFILE=pii-infrastructure -v "$HOME/.aws:/root/.aws:ro" inflation-classifier:latest s3://bucket/input.csv s3://bucket/output.csv`

## AWS Batch
You can launch a batch process from your local environment.  
Create a job and pass in a parameter for the input S3 bucket.  

```bash
aws batch submit-job \
  --job-name job-from-aws-cli \
  --job-queue pii-batch-queue-dev \
  --job-definition pii-batch-jobdef-fargate-dev \
  --parameters input_s3_uri=s3://bucket/input.csv,output_s3_uri=s3://bucket/output.csv
```

## S3 input and output behavior

The CLI supports both local paths and S3 URIs for both input and output arguments.

When an S3 URI (`s3://...`) is used:
- the classifier will parse bucket and key
- for input: read the S3 object and load CSV
- for output: write the resulting CSV back to S3
- run the existing classification flow
- progress and logs are written to `stdout`
- in `--evaluate` mode, the summary report is written to `stdout`

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
- read up on whether or not containers executing a process as a root user is a concern.
- 