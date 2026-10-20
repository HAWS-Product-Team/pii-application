Feature: Spending History API on AWS API Gateway

  Background:
  * url 'https://5m782q7f45.execute-api.us-east-1.amazonaws.com/dev'

  Scenario: Submit a valid PDF spending-history batch
    Given path 'spending-history'
    And request
      """
      {
        "files": [
          {
            "filename": "jan.pdf",
            "fileSizeBytes": 1048576
          },
          {
            "filename": "feb.pdf",
            "fileSizeBytes": 2097152
          }
        ]
      }
      """
    When method post
    Then status 200
    And match header Content-Type contains 'application/json'
    And match header Access-Control-Allow-Origin == '*'
    And match response.ticketId == '#string'
    And match response.secret == '#string'
    And match response.uploadPrefix == 'uploads/' + response.ticketId + '/'
    And match response.expectedFileCount == 2
    And match response.expiresInSeconds == '#number'
    And match response.uploads == '#[2]'
    And match response.uploads[0].filename == 'jan.pdf'
    And match response.uploads[0].key == 'uploads/' + response.ticketId + '/jan.pdf'
    And match response.uploads[0].uploadUrl == '#string'
    And match response.uploads[1].filename == 'feb.pdf'
    And match response.uploads[1].key == 'uploads/' + response.ticketId + '/feb.pdf'
    And match response.uploads[1].uploadUrl == '#string'


  Scenario: Reject missing files field
    Given path 'spending-history'
    And request
      """
      {
        "spending": 100,
        "category": "food"
      }
      """
    When method post
    Then status 400
    And match header Access-Control-Allow-Origin == '*'
    And match response.error == '#string'

  Scenario: Reject empty files list
    Given path 'spending-history'
    And request
      """
      {
        "files": []
      }
      """
    When method post
    Then status 400
    And match response.error contains "cannot be empty"

  Scenario: Reject non-PDF filename
    Given path 'spending-history'
    And request
      """
      {
        "files": [
          {
            "filename": "jan.csv",
            "fileSizeBytes": 1048576
          }
        ]
      }
      """
    When method post
    Then status 400
    And match response.error contains ".pdf"

  Scenario: Reject file smaller than minimum size
    Given path 'spending-history'
    And request
      """
      {
        "files": [
          {
            "filename": "jan.pdf",
            "fileSizeBytes": 1024
          }
        ]
      }
      """
    When method post
    Then status 400
    And match response.error contains "below minimum allowed"

  Scenario: Reject duplicate filenames case-insensitively
    Given path 'spending-history'
    And request
      """
      {
        "files": [
          {
            "filename": "jan.pdf",
            "fileSizeBytes": 1048576
          },
          {
            "filename": "JAN.pdf",
            "fileSizeBytes": 1048576
          }
        ]
      }
      """
    When method post
    Then status 400
    And match response.error contains "Duplicate filename"