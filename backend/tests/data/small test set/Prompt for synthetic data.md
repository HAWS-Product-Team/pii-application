# Synthetic purchase data

# Small set
Generate synthetic consumer purchase transaction data for a family of four. Output as CSV with columns: date, item_description, quantity, unit_price, total_price, category, difficulty.
Date range: January 1 2024 through December 31 2024. Generate approximately 300 rows with a roughly even distribution across all categories.
Categories (use exactly these labels): Housing; Food and Beverages; Transportation; Medical Care; Energy; Household Furnishings and Operations; Apparel; Recreation, Education, and Communication
Include recurring monthly items: mortgage payment, gas/electric utility bill, car insurance, internet service.
For item_description, vary the style to reflect real-world receipts and bank statements — sometimes a merchant name ("Kroger"), sometimes a product name ("organic whole milk 1 gal"), sometimes an ambiguous abbreviation ("SQ FRESH MKT"), and sometimes a vague description ("online subscription").*
For the difficulty column, label each row as one of: easy (clearly belongs to one category), medium (could plausibly fit two categories), or hard (genuinely ambiguous — e.g., "Apple.com/bill" could be Recreation or Communication; "gym membership" could be Medical Care or Recreation).
Include at least 30 hard examples and 60 medium examples. The remaining rows can be easy.
