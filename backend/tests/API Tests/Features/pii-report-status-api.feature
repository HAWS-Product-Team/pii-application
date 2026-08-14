Feature: PII Report Status API on AWS API Gateway

  Background:
    * url 'https://5m782q7f45.execute-api.us-east-1.amazonaws.com/dev/'

  Scenario: Get PII report status without authorization
    Given path '/pii-report-status'
    When method get
    Then status 401