# Change classifier contract
To make the contract with classifier homogenous with the other pipeline tools, we need to change the contract of the classifier.

# Contract changes
The cli presently takes one positional argument `csv_path` and prints to stdout the results of the classification.
Now I want to change to requiring two positional arguments:
<input-csv-file> and <output-csv-file>.  Those arguments can be to local file system or S3 URIs.

# Acceptance Criteria
- Can run classification as `inflation-classifier input.csv output.csv`
- Optional flags are unchanged
- The classified CSV data (original data plus the new 'category' column) is written to `<output-csv-file>` and no longer goes to stdout.
- When `--evaluate` is used:
    - The classified CSV with predicted categories is still saved to `<output-csv-file>`.
    - The evaluation summary report continues to be written to `stdout` in its current text format.
- The two positional arguments are required.
- error messages are written to `stderr`.
- Logs, progress messages sent to `stdout`. 
- If the required arguments are not provided, the CLI displays a helpful error message and usage information.
- The CLI usage/help is updated to reflect the new contract.
- S3 URIs for both input and output are supported using default environment credentials.