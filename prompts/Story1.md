# Story 1: Anonymize Test Data

## Goal
Create a Python script to anonymize test data in `backend/tests/spending-data/personA` to prevent Personal Identifiable Information (PII) from being exposed in the public repository.
The code for the tool should be located in a module called `anonymizer.py` in `backend/tests/data-tools/apps/anonymizer`.

The core implementation must live in:
`backend/tests/data-tools/apps/anonymizer/anonymizer.py`

The tool must preserve `.webarchive` validity so existing tests can still load and parse the HTML content.

## Non-goals (Scope Boundaries)
- We are not attempting perfect PII detection for all possible PII types.
- Only the PII categories listed below must be detected and replaced.
- Do not modify non-text/binary resources (images, PDFs, etc.).

## Inputs / Outputs
### Inputs
- A directory path. The tool recursively finds files ending in `.webarchive` (case-insensitive).
- Apple `.webarchive` files are Binary Property List (bplist) structures.

### Outputs
- Either overwrite in place OR write to a separate output directory while preserving relative paths.
- Output files must remain valid `.webarchive` files (plist must load; structure preserved; only text payloads changed).

## What to Parse Inside a .webarchive
The tool must traverse:
- `WebMainResource`
- `WebSubresources` (if present)
- `WebSubframeArchives` (if present; recursively, because subframes can contain nested webarchives)

Only resources with text payloads should be processed:
- Process if MIME type is `text/html` or `text/plain`
- (Optional, if encountered in the dataset): `application/json`
- Skip everything else (treat as binary and leave unchanged)

## PII Categories to Replace
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
- The script should accept a directory path as an argument and recursively process all `.webarchive` files.
- Output should be written to the same directory structure as the input files.
- The script can accept an option --output-dir to specify an alternate output directory.
- When run without arguments, the script should print usage information.

Exit codes:
- 0 on success
- non-zero on invalid input or processing error

## Reporting / Verification
At the end, print a summary:
- total `.webarchive` files discovered
- total processed (and total written if not dry-run)
- total skipped (e.g., unreadable)
- replacements applied:
  - totals per PII category
  - grand total

Definition: “replacements applied” = number of substitutions that changed text (not just matches found).

## Technical Constraints
- **Language**: Python 3.x
- a regex-only solution is acceptable.
- **Libraries**: Use standard libraries where possible (e.g., `plistlib` for handling binary plists). If external libraries like `BeautifulSoup` or `lxml` are used for HTML parsing, they must be documented.
- **Integrity**: The resulting `.webarchive` file must remain a valid, readable Apple webarchive file so 
that existing tests can still parse the HTML content. Preserve plist structure and all non-text payload bytes unchanged.

## Tests
Write unit tests for 'anonymizer.py' that cover:
- Parsing and writing a minimal synthetic `.webarchive` plist (round-trip validity)
- Replacement behavior for each PII category
- Idempotency (second run produces identical output)
- Recursive handling of `WebSubframeArchives` (at least one nested case)

Tests must not embed real PII. Use synthetic but PII-shaped strings in fixtures.

## Acceptance Criteria
- Running the tool on the input directory produces anonymized `.webarchive` files that:
  - can be loaded using `plistlib` (no errors), and
  - remain usable by existing tests that parse HTML/text content.
- Dry-run mode:
  - writes no files, and
  - prints a summary report including files discovered/processed/skipped and replacements applied (per PII category and total).
- Re-running the tool on already anonymized output results in:
  - 0 additional replacements applied, and
  - no file writes (or file content changes), i.e., the tool must not re-randomize already-anonymized placeholders.

Placeholders may be chosen non-deterministically on first anonymization, but the output format must be recognizable so that subsequent runs do not modify already-anonymized values.

