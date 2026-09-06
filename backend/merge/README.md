# CSV Merge Service

Merge a directory of single-schema CSV files into a single consolidated CSV file.

Supports both local filesystem paths and Amazon S3 URIs (`s3://...`).

## CLI Usage

```bash
# Basic usage (quiet by default, merges files without adding source column)
python -m merge.cli <input_dir> <output_file>

# Verbose mode (includes origin filename column and displays per-file row counts)
python -m merge.cli <input_dir> <output_file> --verbose

# Custom source column name (used when --verbose is active)
python -m merge.cli <input_dir> <output_file> --verbose --source-column origin_file

# S3 URIs
python -m merge.cli s3://bucket/tickets/123/csv s3://bucket/tickets/123/merged.csv
```

### Options

- `input`: (Positional) Input directory or `s3://` prefix containing CSV files to merge (must be a directory).
- `output`: (Positional) Destination CSV file path or `s3://` URI where merged output is written.
- `-v`, `--verbose`: Write the origin filename source column into the merged CSV and display per-file row count summary.
- `--source-column`: Name of the appended origin-filename column when `--verbose` is used (default: `source_file`).
- `-h`, `--help`: Show help message and exit.
