# pii-application
A web application that computes Personal Inflation Index

# user workflow
1. user discovers app
2. user learns about PII and why its more valuable than CPI
3. user learns how to collect data for PII
4. user uploads data to app
5. user views their PII as compared to CPI and views other analysis:
   - prediction of future PII
   - what parts of their spending is experiencing greatly different inflation than CPI
  
# steps to compute PII
these are steps that the application needs to do in order to compute PII. (Lance: not all these are correct but im putting them here to revise later.)
	1.	Exploratory analysis: catagorize data using ML
	2.	Price tracking: For repeat purchases, calculate price changes month-over-month
	3.	(necessary?)ML feature engineering: Create features like average price per category, seasonality, trend
	4.	(necessary to train a model for each user im order to predict future?) Model building: Train models to predict inflation in your spending patterns
	5.	Validation: Compare your personal inflation to official CPI—where do they diverge?
