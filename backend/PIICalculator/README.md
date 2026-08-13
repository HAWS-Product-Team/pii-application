# PIICalculator

A tool to calculate Personal Inflation Index (PII) from classified purchase data.

## Usage

You can run the PII calculator from the command line:

```bash
pii-calculator <input_csv_path> <output_json_path>
```

### Arguments

* `input_csv_path`: Path to the input CSV file containing classified purchases. This can be a local file path or an S3 URI (e.g., `s3://bucket/path/to/classified.csv`).
* `output_json_path`: Path to the output JSON file where the report will be saved. This can be a local file path or an S3 URI (e.g., `s3://bucket/path/to/report.json`).

### Behavior

* The tool will write the JSON report to the specified `output_json_path` and print progress messages to `stdout`.

## Environment Variables

* `MAXCSVFILESIZE`: Maximum allowed size of the input CSV file in MB (default: 20).

## CSV Requirements

The input CSV must contain the following columns:
* `date`: The date of the purchase.
* `item_description`: A description of the item.
* `total_price`: The total price of the purchase.
* `category`: The category of the purchase (e.g., Housing, Food and Beverages, etc.).
