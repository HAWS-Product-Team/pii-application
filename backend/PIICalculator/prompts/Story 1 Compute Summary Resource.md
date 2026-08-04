# User Story: Compute summary resource

## Title
As a user, I want to process my purchase history CSV and compute a personal inflation index by category, so that I can 
understand my experienced inflation over time.  This work will be in a python script at `backend/PIICalculator`. The 
resulting JSON will be output to stdout.

## Input
A CSV file where each row represents a single purchase with the columns:
- `cost` — the amount (numeric)
- `item` — the item name/description
- `category` — one of 8 CPI-based categories
- `date` — the purchase date

## Processing Steps

**Step 1 — Category Totals**
Read the CSV, group rows by `category`, and sum `cost` within each of the 8 categories to produce a total spend per category.

**Step 2 — Month-over-Month Deltas**
Determine the timeframe spanning the data. For each consecutive month in the period, compute the difference in spending within each category versus the prior month. Repeat across the entire loaded period.

**Step 3 — Weights**
For each category, compute its weight as its share of total spending (category total ÷ sum of all category totals across the period).

**Step 4 — Inflation**
Compute the inflation experienced per category over the period, then combine the per-category inflation with the weights to produce a single overall (weighted) inflation index across all categories.

## Output
Print a JSON object to standard out (stdout).

## Acceptance Criteria
- All 8 categories are represented, even if a category has zero spend.
- Weights across all categories sum to 1.0.
- The overall inflation index is the weight-weighted aggregate of per-category inflation.
- Output is valid JSON printed to stdout.
- The schema is **extensible**: information is carried in a `list`, and every entry is self-describing via a `type` field so new feature types can be added later without breaking consumers.
  - `type: "range_inflation"` → the overall inflation across the full range of uploaded data.
  - `type: "category_inflation"` → inflation for a single category.

## Proposed JSON Format

```json
{
  "reportId": "12345",
  "generatedAt": "2026-07-11T22:00:00Z",

  "period": {
    "start": "2024-01",
    "end": "2024-12"
  },

  "summary": {
    "pii": 7.2
  }

  "_links": {
    "self": { "href": "/reports/12345" }
  }
}
```

### Why this shape is extensible
The top-level `data` key is a **list**, and each element has a `type` discriminator. To add a future feature
(e.g., month-over-month series, forecasts, per-item breakdowns), you append a new object with a new `type`
(like `"monthly_delta"` or `"forecast"`) without altering existing consumers — they simply filter on the `type`
values they understand.