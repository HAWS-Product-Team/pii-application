# How to Download Your Purchase History for a Personal Inflation Index

## Why This Matters

Building a personal inflation index requires granular transaction data spanning months or years. This data tells the story of what you actually pay for the things you buy—not what the average consumer pays. By collecting your purchase history now, you can:

- **Track real price changes** in items you buy regularly (milk, gas, coffee, utilities)
- **Identify spending patterns** and category-specific inflation
- **Create a baseline** for machine learning models that predict your personal inflation
- **Detect anomalies** when prices spike unexpectedly in your favorite products
- **Compare personal vs. national inflation** to see if you’re beating or losing to the CPI

The good news: most financial institutions make this data available. The challenge: they each do it differently. This guide walks you through the fastest routes.

-----

## Before You Start: The Big Picture

**What you’re looking for:** Transaction date, merchant/category, amount, and ideally the item description or category.

**The easiest path:** Start with your credit card(s) and bank account, as these offer direct CSV exports. Then tackle Amazon separately if needed.

**Pro tip for bulk downloading:** If you have multiple credit cards or bank accounts, consider using aggregator services (see “Advanced Tools” section below) to pull everything into one place.

-----

## Amazon

**Estimated time: 10-20 minutes for a few years of history**

Amazon is the trickiest because it doesn’t offer a one-click CSV export. However, there are workarounds.

### Option 1: Manual Download (Recommended for Most Users)

1. Go to **Amazon.com** and sign in
1. Navigate to **Returns** or click your account name → **Returns & Orders**
1. You’ll see your order history displayed in a paginated list (typically 10 orders per page)
1. **Scroll through or use the browser’s “Save as HTML”** to capture each page
- Right-click → **Save as** → Save as type: **HTML File (.html)**
- This preserves the structure and all order details
1. Repeat for each page, or see Option 2 for automation

**What you get:** Date, product name, price, order ID. This is the most detailed view.

**Estimated time:** 5 minutes per year of orders (if you have ~50-100 orders/year)

### Option 2: Use a Browser Extension or Script (Fastest)

For hundreds of orders, manually saving pages is tedious. Use one of these tools:

**Browser-based:**

- **Takout Google Takeout** (if you use Google Pay on Amazon): Exports transaction history
- **Amazon Order History Reporter** (browser extension for Chrome): Automatically exports all visible orders as CSV in one click
  - Search for it in Chrome Web Store, install, then click the extension icon on your Orders page

**Python script (for technical users):**

- Amazon provides access to order history via their API with MWS (Marketplace Web Service)
- Alternatively, use Selenium or BeautifulSoup to scrape your own orders programmatically

**Estimated time:** 2-3 minutes

### Option 3: Amazon Prime Account Page

If you have Prime, you can sometimes view transaction history linked to your Prime account:

1. Go to **Amazon Prime** → **Prime Video** → **Account & Settings**
1. Some billing sections show historical charges (though this is payment-level, not order-level)

**Estimated time:** 2 minutes, but less detailed data

### Parsing Amazon Data

Once you download HTML files, you can either:

- **Manually copy-paste** key data into a spreadsheet
- **Parse with Python:** Use BeautifulSoup to extract dates, titles, and prices from HTML files
- **Optical Character Recognition (OCR):** Screenshot and OCR if needed

-----

## Credit Cards

**Estimated time: 5-10 minutes per card**

Most credit card companies offer straightforward transaction exports. This is one of your best sources.

### Major Credit Card Companies

**American Express**

1. Go to **www.americanexpress.com** and sign in
1. Click **Account** → **Statements**
1. Select the date range you want
1. Look for **Download** or **Export** button (usually offers CSV, OFX, or PDF)
1. Choose **CSV** for the easiest machine learning input

**Visa (Chase, Bank of America, Discover, etc.)**

The process varies by bank that issues the card, so check your specific bank below. However, most Visa issuers follow this pattern:

1. Sign in to your card’s online portal
1. Navigate to **Transactions** or **Statement Activity**
1. Select your date range (many allow 6+ months back; some allow 7 years)
1. Look for **Download**, **Export**, or **Get Transactions**
1. Select **CSV**, **OFX**, or **QFX** format

**Discover**

1. Log in to **www.discover.com**
1. Click **Account Overview**
1. Select the account and statement period
1. Click **Download Transaction Details** → **Select CSV**

**Capital One**

1. Log in to your account
1. Go to **Statements** or **Transactions**
1. Select date range
1. Click **Download** or **Export** → **CSV**

**Citi / Citibank**

1. Log in to **www.citibank.com**
1. Click **Statements** → select the card and date range
1. Click **Export Transactions** → choose **CSV** or **OFX**

**Best Practices:**

- Download at least 12-24 months of history for meaningful trends
- If available, use the longest date range the system allows (many allow 5+ years)
- Save files with naming convention: `[CardName]_[StartDate]_[EndDate].csv`
- Check the CSV format—some include merchant category codes (MCC), which are useful for categorization

**Estimated time per card:** 5 minutes

**Total for 3 cards:** 15 minutes

-----

## Banks

**Estimated time: 5-10 minutes per account**

Your checking and savings accounts provide merchant-level detail that credit cards might not capture (smaller purchases, transfers, subscription payments).

### Major Banks

**Chase (Chase Bank)**

1. Log in to **www.chase.com**
1. Select the account
1. Click **Transactions** or **Activity**
1. Use the date range filter
1. Look for the three-dot menu or **Download** option
1. Select **CSV** or **OFX**

**Bank of America**

1. Log in to **www.bankofamerica.com**
1. Select your account
1. Click **Statements & Documents** → **Statements**
1. Or click **Activity** for recent transactions
1. Click **Download** → Choose **CSV** or **OFX**

**Wells Fargo**

1. Log in to **www.wellsfargo.com**
1. Select account
1. Click **View Statements** or **Transactions**
1. Select date range
1. Click **Download Transactions** → **CSV** or **OFX**

**Citi / Citibank**

1. Log in to account
1. Select the checking/savings account
1. Go to **Account Activity** or **Statements**
1. Look for **Download Activity** → **CSV**

**Capital One 360 (Online Bank)**

1. Log in to your account
1. Go to **Transactions**
1. Select the account and date range
1. Click **Download** → **OFX** or **CSV**

**Credit Unions**

- Most credit union portals have similar export features under “Statements” or “Transactions”
- If not visible, contact your credit union—they typically offer downloads via secure request

**Generic advice for any bank:**

- If you can’t find an export button, look under **Settings** → **Export**, **Download**, or **Statements**
- Some banks limit export to recent transactions (30-90 days); call them to request older statements
- OFX format is more standardized; CSV is easier to manipulate

**Estimated time per account:** 5-10 minutes

**Total for 2 accounts:** 10-20 minutes

-----

## Other Sources Worth Downloading

### Subscriptions & Recurring Charges

- **Apple ID** (Settings → [Your Name] → Media & Purchases → Purchase History)
- **Google Play** (Payments profile → Transactions)
- **Spotify, Netflix, etc.:** Check your account settings for billing history

**Estimated time:** 2-3 minutes per service

### Utilities

- **Electric/Gas:** Most utility companies now offer online account access with monthly bills
- Download as PDF and extract the charge amount, or look for data export options
- **Water, Internet, Phone:** Same approach

**Estimated time:** 5-10 minutes

### Retailer Loyalty Programs

- **Whole Foods, Kroger, Safeway, Target, Walmart:** Most loyalty programs track purchases
- Log in, find **Purchase History** or **Receipts**, download or screenshot
- Some offer email exports if requested

**Estimated time:** 5 minutes per retailer

-----

## Advanced Tools for Bulk Downloading

If you have dozens of accounts or want to centralize data collection, consider these tools:

### 1. **Plaid** (Developer-Friendly)

- Aggregates transactions from 12,000+ institutions
- Free tier available; you can build scripts around their API
- Best for: People comfortable with coding

### 2. **Personal Capital** (Free)

- Free financial dashboard that aggregates all accounts
- Allows you to view and export transaction history
- Less granular than individual downloads but convenient

### 3. **Mint** (Acquired by Intuit, being phased out)

- If you have existing Mint data, export before sunset
- Consider migrating to Intuit’s newer tools

### 4. **YNAB (You Need A Budget)**

- Integrates with banks and credit cards
- Allows export of categorized transactions
- Paid service (~$15/month) but excellent for personal finance tracking

### 5. **Python/Selenium Automation**

For advanced users: Write a script that logs into each site and downloads data automatically

- Libraries: `selenium`, `requests`, `beautifulsoup4`
- Caution: Some terms of service restrict automated access; use carefully

-----

## Data Consolidation & Cleaning

Once you’ve downloaded everything, you’ll need to combine it into a single dataset.

### Step 1: Standardize Formats

- Convert all files to CSV
- Create columns: `Date`, `Merchant`, `Category`, `Amount`, `Source` (Amazon/Chase/Bank)

### Step 2: Parse & Clean

Use a spreadsheet tool (Excel, Google Sheets) or Python:

```python
import pandas as pd

# Load multiple CSVs
amex = pd.read_csv('amex_history.csv')
chase = pd.read_csv('chase_history.csv')

# Standardize column names
amex = amex.rename(columns={'Transaction Date': 'Date', 'Description': 'Merchant', 'Amount': 'Amount'})
chase = chase.rename(columns={'Trans Date': 'Date', 'Description': 'Merchant', 'Debit': 'Amount'})

# Combine
combined = pd.concat([amex, chase], ignore_index=True)
combined.to_csv('personal_transactions_combined.csv', index=False)
```

### Step 3: Categorize

Many transactions will have merchant category codes or descriptions:

- Use keyword matching to auto-categorize (grocery, fuel, dining, utilities, etc.)
- Manually categorize edge cases
- Libraries like `categorizer` can automate this

-----

## Timeline & Effort Summary

|Source                 |Time         |Difficulty|Data Quality |
|-----------------------|-------------|----------|-------------|
|Credit Card (1)        |5 min        |Very Easy |Excellent    |
|Bank Account (1)       |5 min        |Very Easy |Excellent    |
|Amazon                 |10-20 min    |Easy      |Good         |
|Utilities              |5-10 min     |Easy      |Good         |
|Subscriptions          |5 min        |Very Easy |Fair         |
|**Total (basic setup)**|**30-50 min**|**Easy**  |**Excellent**|

**To get 2+ years of data with full history:** Plan for 1-2 hours of work across all sources. The payoff: a rich dataset for ML training.

-----

## Pro Tips for Maximum Efficiency

1. **Batch your downloads:** Set aside 30-60 minutes and do all accounts at once rather than spreading it out
1. **Use password managers:** If you use a password manager (1Password, Bitwarden), you can quickly log into each account
1. **Keep file naming consistent:** `[Institution]_[Account]_[StartDate]_[EndDate].csv` makes it easier to organize later
1. **Download the longest available history:** Don’t just grab the last 3 months; most institutions allow 5-7 years
1. **For Amazon, use the browser extension:** If you have hundreds of orders, the manual HTML approach will frustrate you—the extension saves hours
1. **Test your pipeline:** Download one month of data from each source, test your parsing code, then do bulk downloads
1. **Schedule quarterly downloads:** Set a recurring calendar reminder to download data every 3 months so you don’t lose history

-----

## Troubleshooting

**“I can’t find the download/export button”**

- Look in account settings, not just the transaction view
- Try the browser’s Find function (Ctrl+F / Cmd+F) to search for “download” or “export”
- Contact customer support—they can usually email you data directly

**“The date range I need isn’t available”**

- Call the institution and ask if they can provide older statements
- Many will email you historical data upon request
- For banks, legally they must provide statements going back several years

**“The CSV format is weird or missing data”**

- Try downloading as OFX format instead (more standardized)
- Open in Excel or a text editor to inspect the structure
- Some banks have different formats for checking vs. savings

**“Amazon is only showing recent orders”**

- Amazon only displays ~5 years of order history max
- For older orders, check old email receipts
- The Amazon Orders page should go back further if you scroll
