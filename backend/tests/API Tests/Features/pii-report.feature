Feature: Spending History API on AWS API Gateway

  Background:
    * url 'https://5m782q7f45.execute-api.us-east-1.amazonaws.com/dev/'

Scenario: Submit spending history
    Given path '/pii-report'
    And header Authorization = "Bearer anything"
    When method get
    Then status 200
    And match response ==   
    """
    {
      "message": "Your personal inflation is 14.",
      "links": [
        {
        "rel": "self",
        "href": "/pii-report"
        }
      ]
    }
    """