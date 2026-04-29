# pii-application 
A web application that computes a user's Personal Inflation Index 

# source code organization
- backend: python code for data ingestion and inflation computation
- frontend: react code for user interface and data visualization

No code between the two folders is refeferenced directly. Communication between the two folders is done via Web API calls.

# user workflow
1. user discovers app
2. user learns about PII and why its more valuable than CPI
3. user learns how to collect data for PII
4. user uploads data to app
5. user views their PII as compared to CPI and views other analysis:
   - prediction of future PII
   - what parts of their spending is experiencing greatly different inflation than CPI
  
# front end workflow
1. React app gets CSV and gives to API, a ticket number (random number) is returned to the react app.
2. React app polls API for an update using that ticket number. The API returns "in progress" until the report is ready.
3. React app polls API and gets a json message that contains the report.

# backend workflow 
1. API puts a message on SQS
2. AWS Batch sees message on SQS which contains the ticket number
3. AWS Batch executes Data Pipeline
	4.	PDF is converted to CSV (window of data theft vulnerability starts here)
 	5.	CSV is normalized
 	6.	normalized data is annonymized (ending the window of personal information vulnerability)
  	7.	annonymized data is catagorized
   	8.	PII Calculator generates PII report
   	9.	CPI as added to report (is it wise to add that dependency into our data pipeline)? Or is it acquired by the front end (depenency is in the front end)?
   	10.	AWS Batch puts on SQS that the report is done for the ticket number.
11.	When API passes report to front end, it puts on SQS that the report was delivered
12.	AWS batch sees "Report Delivered" message for Ticket Number and deletes the data associated with that ticket number (ending the window of data theft vulnerability removed)

React app polls (again) with ticket number and gets json response back from API and then presents visualization to the user.  The data associated with the ticket number is removed.
  
# compute PII workflow
these are steps that the application needs to do in order to compute PII. (Lance: not all these are correct but im putting them here to revise later.)
	1.	Exploratory analysis: catagorize data using ML
	2.	Price tracking: For repeat purchases, calculate price changes month-over-month
	3.	(necessary?)ML feature engineering: Create features like average price per category, seasonality, trend
	4.	(necessary to train a model for each user im order to predict future?) Model building: Train models to predict inflation in your spending patterns
	5.	Validation: Compare your personal inflation to official CPI—where do they diverge?

-----


# Personal Inflation Tracker - Architecture & Roadmap
## Data Flow

### 1. Data Ingestion

Users can provide their purchase history through:

#### Download Amazon Order History

Amazon allows users to download:

- Order History Reports (CSV format)
- Item name
- Category
- Order date
- Item price
- Quantity

-----

### 2. Data Cleaning & Normalization

Process each order by:

- Parsing structured fields (date, price, quantity, description)
- Normalizing product names (remove extra whitespace, standardize formatting)
- Extracting units (e.g., “120-count paper towels” → per-unit price)
- Handling edge cases (variety packs, weight-based items)
- Inferring category (CPI category) using ML text classification (DistilBERT, BERT, or simpler models)

-----

### 3. Category Classification Model (ML)

Use a model to categorize items automatically.

**Inputs:** Item name + description  
**Outputs:** Category (Groceries, Household, Electronics, Clothing, etc.)
Read more about the model [here](model%20for%20classification.md).

-----

### 4. Price Time Series Construction

Group purchases by:

- Category
- Item SKU (inferred if possible)
- Unit-normalized prices

Compute:

- Price per unit over time
- Rolling averages (e.g., 30-day, 90-day)
- Year-over-year (YoY) and month-over-month (MoM) price changes

-----

### 5. Personal Inflation Model

#### Step 1: Compute Category-Level Inflation

For each category `c`:

```
Inflation_c(t) = (AvgPrice_c(t) - AvgPrice_c(t-12)) / AvgPrice_c(t-12)
```

Where:

- `AvgPrice_c(t)` = average price in category `c` at time `t`
- `AvgPrice_c(t-12)` = average price 12 months prior

#### Step 2: Weight by Personal Spending

Let `w_c` = user’s spending share on category `c`:

```
w_c = TotalSpend_c / TotalSpend
```

#### Step 3: Compute Personal Inflation Index

```
PersonalInflation(t) = Σ_c (w_c × Inflation_c(t))
```

This produces a CPI-like index weighted by the user’s actual consumption basket.

-----

## Optional ML Enhancements

### 1. Anomaly Detection

Identify and exclude:

- Subscription renewals (recurring charges)
- Gifts (personal consumption distortions)
- One-time big-ticket items (which skew inflation metrics)

### 2. Product Similarity Clustering

Group similar products so that:

- “Kirkland paper towels – 12-pack”
- “Bounty paper towels – 8-pack”

…are treated as the same essential product type for price tracking.

Use: Fuzzy matching, embeddings (Sentence-BERT), or clustering (K-means on TF-IDF vectors).

### 3. Forecasting

Predict a user’s future costs using:

- **Prophet** (good for seasonality)
- **ARIMA** (classical time-series)
- **LSTM** (deep learning approach)

-----

## Privacy & Legal Notes

- ✅ **Do:** Let users voluntarily upload their Amazon order CSV
- ✅ **Do:** Process data locally or with strong anonymization
-  ? **caution:** Scrappimg Amazon or any retailer may resukt in them blocking our site
- ❌ **Don’t:** Store raw data longer than necessary
- ✅ **Do:** Be transparent about what data you collect and retain

-----

## Minimum Viable Product (MVP) Flow

1. User uploads Amazon order history CSV
1. Parse and clean data (dates, prices, quantities)
1. ML model categorizes each item
1. Compute category weights (personal spending shares)
1. Calculate personal inflation metrics
1. Display:
- Last 24+ months of inflation
- Category-level breakdown
- Top drivers of personal inflation
- Comparison to national CPI

-----

## Next Steps

Choose what to build first:

- [ ] Sample Python code for ingestion & inflation computation
- [ ] ML architecture diagram
- [X] Frontend mockups
- [X] Tech stack recommendation (serverless, containerized, etc.)
- [ ] Sample data & test cases

-----

## Tech Stack Considerations

**Backend:**

- Python (pandas, scikit-learn, transformers)
- Serverless (AWS Lambda--not good as it has limits, AWS Batch--promising) or 
containerized (Docker)--most expensive

**ML/NLP:**

- Hugging Face Transformers (for classification)
- scikit-learn (for clustering, TF-IDF)
- Prophet or statsmodels (for forecasting)

**Frontend:**

- React + Plotly/Chart.js (interactive visualizations)

-----

## Known Limitations & Future Work

- **Unit extraction** is non-trivial for real-world data (variety packs, weight-based items)
- **Seasonality** needs careful handling (winter coats shouldn’t spike clothing inflation)
- **Minimum data requirement:** ~6 months of purchase history for meaningful results
- **Category coverage:** Amazon’s native categories should be leveraged where available
- **Performance:** Consider lazy-loading and caching for large order histories (10,000+ items)
