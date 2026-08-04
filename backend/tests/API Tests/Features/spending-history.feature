Feature: Spending History API on AWS API Gateway

  Background:
    * url 'https://5m782q7f45.execute-api.us-east-1.amazonaws.com/dev/'

Scenario: Submit spending history
    Given path '/spending-history'
    And request { "spending": 100, "category": "food" }
    When method post
    Then status 200
    And match response ==   
   """
{
  "links": [
    {
      "href": "/pii-report-status",
      "rel": "pii-report-status"
    }
  ]
}
"""