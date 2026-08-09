# No commas in output for classification description
Presently, when outputing the classification: `Recreation, Education, and Communication`, the commas 
foul the CSV parsing. Please change the code to instead output: `Recreation Education and Communication`

Acceptance criteria:
- output from classifier for the classification Recreation, Education, and Communication is: `Recreation Education and Communication`
- automated tests are updated and passing
