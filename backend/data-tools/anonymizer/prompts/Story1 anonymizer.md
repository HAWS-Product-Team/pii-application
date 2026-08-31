# Story 1: Anonymize Test Data

## Goal
Create a Python script to anonymize test data attached to this chat. I want to prevent Personal Identifiable 
Information (personal identifying information) from being exposed in the public repository.

The tool must preserve `.pdf` validity so existing tests can still load and parse the HTML content.

## Non-goals (Scope Boundaries)
- We are not attempting perfect personal identifying information detection for all possible personal identifying information types.
- Only the personal identifying information categories listed below must be detected and replaced.


## Inputs / Outputs
### Inputs
- A path to a file on local disk.

### Outputs
- Write to the same directory a new file with a suffix of `-annon`.pdf

## Personal identifying information Categories to replace
Replace occurrences in text content using realistic placeholders:

- **Full Names**: e.g., "Lance Kind" -> "John Doe"
- **Street Addresses**: e.g., "6 TURTLE ROCK CT" -> "123 Main St"
- **City, State, Zip**: e.g., "THE WOODLANDS, TX 77381" -> "Anytown, CA 12345"
- **Order Numbers**: e.g., "111-1234567-1234567" -> "000-0000000-0000000"
- **Tracking Numbers**: Any visible carrier tracking numbers.
- **Payment Info**: References like "Visa ending in 1234" -> "Card ending in 0000"
- **Email Addresses**: e.g., "lance.kind@example.com" -> "john.doe@example.com"
- **Phone Numbers**: e.g., "(123) 456-7890" -> "(555) 123-4567"
- Reuse anonymized mapping across the files to maintain consistency. For example, if "Lance Kind" is replaced with "John Doe", the same replacement should be applied consistently across all files.
- **Credit Card Numbers**: e.g., "1234 5678 9012 3456" -> "0000 0000 0000 0000"
- **Social Security Numbers**: e.g., "123-45-6789" -> "000-00-0000"
- **Bank Account Numbers**: e.g., "1234567890123456" -> "0000000000000000"

## CLI 
- The script require a file path as an argument to a .pdf
- Output should be written to the same directory as the input files.
- The script can accept an option --output-dir to specify an alternate output directory.
- When run without arguments, the script should print usage information.

Exit codes:
- 0 on success
- non-zero on invalid input or processing error

## Technical Constraints
- **Language**: Python 3.12
- a regex-only solution is acceptable.
- **Libraries**: Use standard libraries where possible (e.g., `plistlib` for handling binary plists).
- **Integrity**: The resulting `.pdf` file must remain a valid, readable file so 
that existing tests can still parse the PDF content.

## Design
- use SOLID coding principles to ensure maintainability and extensibility of the codebase.
- use argparse to parse command-line arguments.

## Tests
Write unit tests for 'anonymizer.py' that cover:
- Parsing and writing a minimal synthetic `.pdf`
- Replacement behavior for each personal identifying information

Tests must not embed real personal identifying information. Use synthetic but personal identifying information-shaped strings in fixtures.

## Acceptance Criteria
- Running the tool on the input directory produces anonymized PDF files `*-anon.pdf` that:
  - can be loaded by a pdf reader
  - remain usable by existing tests that parse pdf content.