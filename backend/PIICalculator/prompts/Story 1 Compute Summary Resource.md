# User Story: Compute summary resource

## Title
As a user, I want to process my purchase history CSV and compute a personal inflation index by category, so that I can 
understand my experienced inflation over time.  This work will be in a python script at `backend/PIICalculator`. The 
resulting JSON will be output to stdout.

## Cli arguments
The CLI executable will be called `pii-calculator` for the script name in the toml file.  The 
python function will use the python lowdash convention.  The script accepts one required positional argument: 
the path to the CSV file. The path also must support 
reading from an S3 bucket, the same as inflation-classifier.  Use the same libraries for this as used in 
inflation-classifier:
```toml
[[package]]
name = "s3fs"
version = "0.4.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "botocore" },
    { name = "fsspec" },
]
sdist = { url = "https://files.pythonhosted.org/packages/d9/9a/504cb277632c4d325beabbd03bb43778f0decb9be22d9e0e6c62f44540c7/s3fs-0.4.2.tar.gz", hash = "sha256:2ca5de8dc18ad7ad350c0bd01aef0406aa5d0fff78a561f0f710f9d9858abdd0", size = 57527, upload-time = "2020-03-31T15:24:26.388Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b8/e4/b8fc59248399d2482b39340ec9be4bb2493846ac23641b43115a7e5cd675/s3fs-0.4.2-py3-none-any.whl", hash = "sha256:91c1dfb45e5217bd441a7a560946fe865ced6225ff7eb0fb459fe6e601a95ed3", size = 19791, upload-time = "2020-03-31T15:24:24.952Z" },
]
```

## Configuration
Configuration for pii-calculator will be passed by environment variables so that they can be easily changed in the Docker
file or passed as command line arguments.

## CSV Input
A CSV file where each row represents a single purchase with at least 
the following columns (order of the columns may be different and there may be other columns which can be ignored):
- `date` — the purchase date
- `item_description` — the item name/description
- `total_price` — the amount (numeric)
- `category` — one of 8 CPI-based categories

Don't assume the report is sorted by date.  Many reports were uploaded and merged into one CSV file.
Input row order is not significant. The calculator must produce the same result regardless of CSV row order. 
The implementation should derive a `YYYY-MM` month from each row’s `date`, aggregate by month and category, 
and sort the aggregated monthly data as needed for month-over-month calculations. 
The normalized CSV does not need to be pre-sorted by date.

### Report quality
Since it's not possible or likely that the user uploads perfect months worth of data due to start and ends of 
billing cycles, exclude the starting month and the ending month from computation for PII.

### Error handling
If there are any errors, exit with a non-zero status, output a human readable message to stderr, 
and output the error message in json format to stdout for later transmission back to the user.
The json will have links to the following resources: self, spending-history, welcome.

### Guardrails

#### max csv filesize
The CSV max file size defaults to 20MB. This setting can be overridden by changing the configuration by stating
how many megabytes to allow:```MAXCSVFILESIZE=200```

#### If the file is too large:
- reject it with a non-zero exit and 
the following error message to stderr: "File size exceeds the maximum allowed limit of 20MB."
- output to stdout a json message that contains: the date the message was created, the error message, and links to the
following resources:
  - `self`
  - `spending-history` (so the user can resubmit their data)
  - `/` (so the user may go back to the home page)

Here is an example error message:
```json
{
  "generatedAt": "2026-07-11T22:00:00Z",
  "message": "The input file size exceeds the maximum allowed limit of 20MB.",
  
  "_links": {
    "self": { "href": "/pii-summary" },
    "spending-history": { "href": "/spending-history" },
    "welcome": { "href": "/" }
  }
}
```

#### If the CSV file contains too little data:
This algorithm requires at least four months of data.  This is defined by having at least one row of data in each 
of four contiguous months.  It is assumed the months on the ends could be incomplete so computation of inflation 
will exclude the months on the ends.
If the CSV file contains less than four months of data then exit with a non-zero status and 
output the following to stderr: `There is too little data for computing inflation.  Please upload a at least 
four months of data.`
- to stdout, output the error message in json format

Here is an example error message:
```json
{
  "generatedAt": "2026-07-11T22:00:00Z",
  "message": "There is too little data for computing inflation.  Please upload a at least four months of data.",
  
  "_links": {
    "self": { "href": "/pii-summary" },
    "spending-history": { "href": "/spending-history" },
    "welcome": { "href": "/" }
  }
}
```

#### Date
Dates must be parseable as ISO-8601 dates, `YYYY-MM-DD`.
Months are represented as `YYYY-MM`.
The period start is one month after the earliest purchase month.
The period end is one month before the latest purchase month.
All calendar months between start and end are included, even if there are no purchases in that month.
The generatedAt value used in output uses ISO 8601 date and time format: "2026-07-11T22:00:00Z"

#### Other input file errors
For invalid input for other reasons that haven't been specified above, write a clear error message to stderr,
write a JSON error response to stdout that contains the same error message, and exit with a non-zero status code.

## Processing Steps
Here are the 8 CPI-based categories:
- Housing
- Food and Beverages
- Transportation
- Medical Care
- Energy
- Household Furnishings and Operations
- Apparel
- Recreation, Education, and Communication

## Calculation Rules
For the data we'll be building a log-linear regression.  Don't use the first month and the last month's data as those
portions will most likely be incomplete measurements.

- The date of the purchase activity is in the `date` column
- Monthly spend for a category is the sum of `total_price` for that category within a calendar month.
- Missing category data during a month is treated as zero spend.
- Inflation values are output as percentages, where `7.2` means `7.2%`.
- Weights are decimals from `0` to `1`.
- Round output numeric values to 4 decimal places.

### The log-linear regression.
For each category:
X = month number
Y_x = ln(category cost), x is one of the eight category types
Use ordinary least squares.
The slope is approximately the monthly inflation rate.
Multiply by 12 to estimate an annualized inflation rate for category Y_x
The log-linear regression approach has a nice property: it naturally handles compounding. A category growing 
2% every month will produce a nearly constant slope even though the dollar increases get larger over time.

**Step 1 — Category Totals**
Excluding the starting month and the ending month in the data, read the CSV, group rows by `category`, and sum `total_price` within each of the 8 categories to produce 
a total spend per category.

**Step 2 — Month-over-Month Deltas**
Determine the timeframe spanning the data. For each consecutive month in the period, compute the difference in spending
within each category versus the prior month. Repeat across the entire loaded period, excluding the first and last
month's worth of data.

**Step 3 — Weights**
For each category, compute its weight as a share of total spending

**Step 4 — Inflation**
Compute the overall inflation by combining the per-category inflation with the category weights.
The category weights are the share of total spending in each category.

## Output
Print a JSON object to standard out (stdout).

## Acceptance Criteria
- All 8 categories are represented, even if a category has zero spend.
- Weights across all categories sum to 1.0.
- The overall inflation index is the weight-weighted aggregate of per-category inflation.
- Output is valid JSON printed to stdout.
- The json schema is staticly typed and extensible.
  -  starts with: "schema_version": "1.0"

## Proposed JSON Format
Don't need to embed the user's ticket number into the json as that will be based on the S3 path which will be created 
by the caller of PII Calculator.  The user's ticket number doesn't show up in the hateoas links as the ticket is in 
a bearer token in a http header.

Here is an example.  The "_links" object will vary by context:
```json
{
  "schema_version": "1.0",
  "generatedAt": "2026-07-11T22:00:00Z",

  "period": {
    "start": "2024-01",
    "end": "2024-12"
  },

  "summary": {
    "pii": 7.2
  },

  "_links": {
    "self": { "href": "/pii-summary" }
  }
}
```