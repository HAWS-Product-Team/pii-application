import os
import pandas as pd
import numpy as np
import json
from datetime import datetime, timezone
from piicalculator.errors import PIICalculatorError, get_timestamp, write_json

CATEGORIES = [
    "Housing",
    "Food and Beverages",
    "Transportation",
    "Medical Care",
    "Energy",
    "Household Furnishings and Operations",
    "Apparel",
    "Recreation, Education, and Communication"
]

def get_max_file_size():
    """Get max file size in MB from environment variable."""
    return int(os.environ.get("MAXCSVFILESIZE", 20))

def pii_calculator(csv_path, output_path):
    print(f"Reading CSV from: {csv_path}")
    
    max_size_mb = get_max_file_size()
    
    # Check file size if it's a local file
    if not csv_path.startswith("s3://"):
        if not os.path.exists(csv_path):
            raise PIICalculatorError(f"Local file does not exist: {csv_path}")
        
        file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise PIICalculatorError(f"File size exceeds the maximum allowed limit of {max_size_mb}MB.")

    try:
        # pandas can read from S3 if s3fs is installed
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise PIICalculatorError(f"Error reading CSV: {e}")

    print("Validating columns and parsing dates...")
    
    # Validate columns
    required_columns = {"date", "item_description", "total_price", "category"}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        raise PIICalculatorError(f"Missing required columns: {', '.join(missing)}")

    # Parse dates
    try:
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.to_period('M')
    except Exception as e:
        raise PIICalculatorError(f"Error parsing dates: {e}")

    # Sort and find period
    all_months = sorted(df['month'].unique())
    if len(all_months) < 4:
         raise PIICalculatorError("There is too little data for computing inflation.  Please upload a at least four months of data.")

    # Determine start and end months (excluding first and last)
    period_start = all_months[1]
    period_end = all_months[-2]
    
    # Check if we have at least 4 contiguous months in the raw data
    # The requirement says: "at least one row of data in each of four contiguous months"
    # Wait, does it mean ANY four contiguous months? Or the WHOLE data must be at least 4 months?
    # "This algorithm requires at least four months of data. This is defined by having at least one row of data in each of four contiguous months."
    # If the months are not contiguous, we might have an issue.
    
    # Let's check for contiguous months in the entire range
    full_range = pd.period_range(start=all_months[0], end=all_months[-1], freq='M')
    
    # We need to find if there's a sequence of 4 contiguous months that have data
    has_data = set(all_months)
    max_contiguous = 0
    current_contiguous = 0
    for m in full_range:
        if m in has_data:
            current_contiguous += 1
            max_contiguous = max(max_contiguous, current_contiguous)
        else:
            current_contiguous = 0
            
    if max_contiguous < 4:
        raise PIICalculatorError("There is too little data for computing inflation.  Please upload a at least four months of data.")

    # Filter data to the period (excluding first and last month)
    mask = (df['month'] >= period_start) & (df['month'] <= period_end)
    period_df = df[mask].copy()
    
    print(f"Computing inflation for period: {period_start} to {period_end}")

    # All calendar months between start and end (inclusive)
    period_months = pd.period_range(start=period_start, end=period_end, freq='M')
    
    # Step 1 & 2: Aggregate by month and category
    monthly_category_spend = period_df.groupby(['month', 'category'])['total_price'].sum().unstack(fill_value=0)
    
    # Ensure all 8 categories are present
    for cat in CATEGORIES:
        if cat not in monthly_category_spend.columns:
            monthly_category_spend[cat] = 0.0
            
    # Reindex to include all months in the period (even if no purchases)
    monthly_category_spend = monthly_category_spend.reindex(period_months, fill_value=0.0)
    
    # Step 3: Weights
    # Total spend per category over the period
    total_spend_per_category = monthly_category_spend.sum()
    grand_total_spend = total_spend_per_category.sum()
    
    weights = {}
    if grand_total_spend > 0:
        for cat in CATEGORIES:
            weights[cat] = total_spend_per_category[cat] / grand_total_spend
    else:
        # If no spend at all, weights are distributed equally? 
        # Or just 0? "Weights across all categories sum to 1.0."
        # If grand_total is 0, we can't really compute weights. 
        # But this should be rare if we have 4 months of data.
        # Let's default to equal weights or something to satisfy the 1.0 sum requirement.
        for cat in CATEGORIES:
            weights[cat] = 1.0 / len(CATEGORIES)

    # Step 4: Per-category inflation via log-linear regression
    category_inflations = {}
    
    # month numbers (0, 1, 2, ...)
    X = np.arange(len(period_months))
    
    for cat in CATEGORIES:
        Y_raw = monthly_category_spend[cat].values
        
        # We need ln(Y). Y must be > 0.
        # If Y is 0, we have a problem.
        # "Missing category data during a month is treated as zero spend."
        # Let's use only months where spend > 0 for the regression.
        valid_indices = Y_raw > 0
        if np.sum(valid_indices) >= 2:
            X_valid = X[valid_indices]
            Y_valid = np.log(Y_raw[valid_indices])
            
            # OLS: slope
            slope, _ = np.polyfit(X_valid, Y_valid, 1)
            # Annualized inflation rate = slope * 12 * 100 (for percentage)
            category_inflations[cat] = slope * 12 * 100
        else:
            # Not enough data points for regression
            category_inflations[cat] = 0.0

    # Overall inflation index
    overall_pii = 0.0
    for cat in CATEGORIES:
        overall_pii += weights[cat] * category_inflations[cat]
        
    # Prepare output
    result = {
        "schema_version": "1.0",
        "generatedAt": get_timestamp(),
        "period": {
            "start": str(period_start),
            "end": str(period_end)
        },
        "summary": {
            "pii": round(overall_pii, 4)
        },
        "_links": {
            "self": {"href": "/pii-summary"}
        }
    }
    
    print(f"Writing result to {output_path}...")
    try:
        write_json(result, output_path)
    except Exception as e:
        raise PIICalculatorError(f"Error writing output JSON: {e}")
    print("Done.")
