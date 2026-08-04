``` markdown
# Story 2: Output CSV with categories

Presently the inflation classifier outputs an evaluation summary which is useful for evaluating the model for 
correctness. Change the CLI so that its default behavior writes the 
input CSV rows to stdout with an added predicted category for each row. 
Preserve the existing evaluation behavior behind a `--evaluate` flag.  The classifier only requires a 
column of the name `item_description` upon which it will run classifaction.  The default CLI behavior is to 
append a `category` column under wich teh classifier will add the classification of each row.

## Behavior
Given an input CSV with an `item` column, the classifier should classify each row based on the value in the 
`item` column.

By default:
``` 
uv run inflation-classifier input.csv
``` 

The CLI writes valid CSV to stdout containing all original input columns in their original order, 
plus a final `category` column containing the predicted category for each row.

When called with:
``` 
uv run inflation-classifier --evaluate input.csv 
```
the CLI writes the existing summary output to stdout, preserving the current summary format.

## Way of working

- Implement the test before the product code using test-driven development.
- Unit test the CLI behavior.
- Unit tests must not load the real ML model; use mocks/fakes for inference.
- Code coverage should exceed 80%

## Acceptance Criteria

- The classifier accepts CSVs with at least the following column: item_description
- CLI default behavior outputs valid CSV to stdout.
- Default CSV output includes all original input columns and adds a final `category` column.
- Categories are generated from the `item_description` column.
- The number of output rows matches the number of input rows.
- Stdout (default) contains only the requested machine-readable output: 
   - 1st row is headers with the new column `category` appended to the end
   - the rows after that are the data with the category for that row listed in the last column 
- Stdout CSV in `--evaluate` mode, outputs evaluation summary (existing functionality) 
at `backend/tests/data/small test set/synthetic_purchases_2024_evaluation_data.csv`
- Manual validation can use backend/tests/data/small test set/synthetic_purchases_2024_evaluation_data.csv
- Errors and diagnostics are written to stderr.
- `--evaluate` preserves the existing evaluation summary behavior and output format.
- If the input CSV is missing the `item_description` column, the CLI exits with a non-zero status code and 
writes a helpful error to stderr.
- If the input CSV already has a last colmun of the name `category`, exit with a non-zero status code and 
write a helpful error message to stderr.
- The work is unit tested, including:
  - default CSV output behavior
  - `--evaluate` behavior
  - CLI argument parsing
  - missing `item_description` column error
  - inference mocked/faked so tests are deterministic and fast
