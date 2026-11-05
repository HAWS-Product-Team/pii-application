Feature: Invoices API on AWS API Gateway

  Background:
    * url 'https://5m782q7f45.execute-api.us-east-1.amazonaws.com/dev/'

  Scenario: Get API root
    Given path '/'
    When method get
    Then status 200
    And match response ==   
    """
      {"links":[{"href":"/spending-history","rel":"upload"}],
        "messages":["Official inflation rates don't reflect your life. Build a personal inflation index based on what you actually buy, and see how prices really affect you."]
      }
    """