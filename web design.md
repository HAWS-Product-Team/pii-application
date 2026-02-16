# React Web Application Design

## Overview
This is a design document for the new React web application. The goal of this project is to create an interactive and user-friendly interface that helps users calculate their personal inflation index.

## Landing Page
The landing page will serve as the entry point for users, providing a clear introduction to the application's purpose and functionality. This section should include:

* A brief header describing the app's purpose
* A concise paragraph explaining what the app does and how it can benefit users
* A link to a guide on how to calculate their personal inflation index
* A call-to-action (CTA) button that prompts users to start calculating their personal inflation index
* Optional: provide an interactive results demo with customizable charts, using libraries like Chart.js or D3.js for visualizations and animations.

![Landing Page Design](/public/LandingPage.png)

## Calculate Personal Inflation Index

This section will contain a CSV prompt where users either import their CSV file containing relevant information, such as income, expenses, and other financial data or export a CSV file. The design should prioritize ease of use and navigation.

* Import/Export CSV file (e.g., columns: income, net worth, savings rate)
* A submit button that triggers the calculation process

![Calculate Page Design](/public/Calculate.png)

## Results Page
The results page will display the calculated personal inflation index, along with relevant insights. This section should be visually engaging and easy to read.

* A brief summary of the user's financial situation and how it relates to the calculation
* Data visualizations using interactive charts (e.g., line graph for expense distribution over time) and tables to compare user's financial data against national averages, highlighting key trends and areas for improvement.
* A "Calculate Again" button to allow user to calculate their personal inflation index again.

![Results Page Design](/public/Results.png)