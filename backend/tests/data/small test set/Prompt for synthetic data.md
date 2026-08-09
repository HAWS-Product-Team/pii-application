# Synthetic purchase data

# Small set for classification evaluation
Generate synthetic consumer purchase transaction data for a family of four. Output as CSV with columns: date, item_description, quantity, unit_price, total_price, category, difficulty.
Date range: January 1 2024 through December 31 2024. Generate approximately 300 rows with a roughly even distribution across all categories.
Categories (use exactly these labels): Housing; Food and Beverages; Transportation; Medical Care; Energy; Household Furnishings and Operations; Apparel; Recreation, Education, and Communication
Include recurring monthly items: mortgage payment, gas/electric utility bill, car insurance, internet service.
For item_description, vary the style to reflect real-world receipts and bank statements — sometimes a merchant name ("Kroger"), sometimes a product name ("organic whole milk 1 gal"), sometimes an ambiguous abbreviation ("SQ FRESH MKT"), and sometimes a vague description ("online subscription").*
For the difficulty column, label each row as one of: easy (clearly belongs to one category), medium (could plausibly fit two categories), or hard (genuinely ambiguous — e.g., "Apple.com/bill" could be Recreation or Communication; "gym membership" could be Medical Care or Recreation).
Include at least 30 hard examples and 60 medium examples. The remaining rows can be easy.

# Large set increasing inflation for classification evaluation and PII calculation testing
Generate synthetic consumer purchase transaction data for a family of four. Output as CSV with columns: date, item_description, quantity, unit_price, total_price, category, difficulty, baseline_price_jan_2024.

Date range: January 1, 2024 through December 31, 2024.
Total rows: 480 (approx. 40 rows per month).
Distribution: Evenly distribute transactions across the 8 CPI categories below.

Categories (use EXACTLY these labels):
1. Housing
2. Food and Beverages
3. Transportation
4. Medical Care
5. Energy
6. Household Furnishings and Operations
7. Apparel
8. Recreation, Education, and Communication

Inflation Model (Linear Monthly Increase):
- Define a "baseline_price_jan_2024" for each item.
- Calculate unit_price for each month such that the price on Dec 31, 2024, is exactly the following % higher than the Jan 1 baseline:
  - Energy: +25%
  - Food and Beverages: +5%
  - Recreation, Education, and Communication: +10% (Note: This replaces "Entertainment")
  - Medical Care: +15%
  - Apparel: +90%
  - Transportation: +10%
  - Housing: +10%
  - Household Furnishings and Operations: +10%

Recurring Monthly Items (Static Pricing):
- Include these 4 items every month: Mortgage Payment, Gas/Electric Utility Bill, Car Insurance, Internet Service.
- These items should NOT follow the inflation model above. Their unit_price should remain constant or have negligible variance (±1%) throughout the year.
- Schedule: Mortgage on 1st, Utilities on 15th, Insurance on 25th. Internet can be any day.

Variable Items (Inflation + Variance):
- All other items (groceries, fuel, clothing, medicine, entertainment) MUST follow the inflation model above.
- Add random noise to unit_price to simulate real-world price fluctuations (e.g., ±5-10% monthly variance around the inflation curve).

Item Description Style:
- Vary style to reflect real-world receipts:
  - Merchant names ("Kroger", "Shell Gas")
  - Product names ("organic whole milk 1 gal")
  - Ambiguous abbreviations ("SQ FRESH MKT", "AMZN Mktp US")
  - Vague descriptions ("online subscription", "payment received")

Difficulty Column (Strict Distribution):
- Label each row as: easy, medium, or hard.
- Strict Count Requirements:
  - 96 rows must be "hard" (genuinely ambiguous, e.g., "Apple.com/bill" could be Recreation or Communication; "gym membership" could be Medical or Recreation).
  - 192 rows must be "medium" (could plausibly fit two categories).
  - 192 rows must be "easy" (clearly belongs to one category).
- Ensure hard examples are distributed across different categories, not just one.

Output Format:
- Pure CSV only. No markdown code blocks, no explanations.
- Copied using Inferencer (inferencer.com)