# Specification: PDF Spending Statements → CSV Converter (Amazon parser)

**Audience:** an agentic AI implementer.
**Repo:** `HAWS-Product-Team/pii-application`, `backend/` (Python). This tool is the "PDF → CSV" step of the backend data pipeline.

---

## 1. Purpose

A command-line Python program that reads a directory of PDF spending statements and
writes one CSV per PDF. This story implements **only the Amazon "Your Orders" page-export
parser** and the surrounding framework (CLI, I/O, source detection, dispatch, error
handling). Other sources (banks, credit cards) are out of scope but the design must make
adding them a matter of writing a new parser class — no changes to the framework.

---

## 2. CLI

- Use `argparse`.
- Two **positional** arguments, in order:
  1. `input_dir` — directory containing PDFs.
  2. `output_dir` — directory to write CSVs into.
- Both accept either a **local path** or an **S3 URI** (`s3://bucket/prefix`), transparently interchangeable.
- Input is **read-only**; output is **write-only**.
- AWS authentication is handled outside the application (standard boto3 credential chain). The program does not manage credentials.

### Argument validation (each → error message to stderr, non-zero exit)
- If `input_dir` is not a directory / does not exist / is unreadable → error.
- If `output_dir` is not a directory / does not exist / is not writable → error.
- If either path is an S3 location the process cannot access (auth/permission failure) → error message naming which path failed.
- A single file passed where a directory is expected is an error ("input must be a directory").

---

## 3. Directory scan

- **Non-recursive**: only entries directly inside `input_dir`.
- Select files whose extension is `.pdf`, **case-insensitive on the extension** (`.pdf`, `.PDF`, `.Pdf` all match), 
**case-sensitive on the filename** otherwise.
- Process each selected PDF independently.

---

## 4. Per-PDF pipeline

For each PDF, in order:

1. **Size check.** If the file is **> 32 MB**, it is an error for that PDF (§8). Skip it.
2. **Text extraction.** Native text extraction only — **no OCR**. Extract text per page and concatenate pages in order into a list of lines.
3. **Source detection.** Inspect the **first 10 lines** of extracted text for a source thumbprint (§5). If no known thumbprint matches → error for that PDF (§8).
4. **Dispatch** to the parser registered for the detected source. In this story only the **Amazon** parser exists.
5. **Parse** into zero or more records (§6).
6. If **zero records** were extracted → error for that PDF (§8), do **not** write a CSV.
7. If **one or more** records → write the CSV (§7).

A failure on one PDF never aborts the run: report it (§8) and move to the next PDF.

---

## 5. Source detection

- Operate on the **first 10 lines** of the extracted text (post-extraction line order, which is **not** visual order — see §6 note).
- Thumbprints (substring match, case-sensitive unless noted):
  - **Amazon** → any of the first 10 lines contains the substring `Amazon`. *(Confirmed present via "Search Amazon" in the page header even though the visual layout shows the logo as an image.)*
  - *(Out of scope, reserved for future parsers — do not implement, but the detector's design must accommodate them):* `Bank` (suffix pattern `*Bank`) → bank; `Visa`, `Mastercard`, `Discover`, `Citibank`, `Chase` → credit card.
- If none match: error whose message is exactly of the form
  `parser not found for first 10 lines:` followed by the ten lines (printed verbatim). Sent to stderr (§8).

---

## 6. Amazon parser — extraction rules

**In scope:** the PDF produced by opening Amazon's **"Your Orders"** history page in Safari and exporting/printing the page as PDF. One such PDF contains **one or more orders** (usually multiple), plus large amounts of page chrome that must be ignored.

> **Critical: extracted text is not in visual order.** In the exported PDF, the extracted
> lines place each order's product description *above* a two-line order header/value pair,
> and page chrome (top nav, "Customers who viewed…", "Similar to your past purchases",
> "Your Browsing History", the footer, sponsored strips) is interleaved and sometimes
> character-corrupted (e.g. `Add a pSroutbemctiiton plan`). The parser must anchor on
> stable structural markers, **not** on line adjacency or the visual layout.

### 6.1 Order anchor (defines a valid record)

A valid order is recognized by a **header line** immediately followed by a **value line**:

- **Header line** matches (case-insensitive): contains `ORDER PLACED`, `TOTAL`, and `ORDER #`, ending with an order number.
  Regex guide: `ORDER PLACED.*TOTAL.*ORDER #\s*([\d-]+)`
- **Value line** (the next line) contains the order date and total.
  Regex guide: `([A-Z][a-z]+ \d{1,2}, \d{4})\s+\$([\d,]+\.\d{2})`

Only blocks that have **both** the header and a matching value line become records. Anything
lacking this pair (all the recommendation/footer/nav content) is ignored. This is what keeps
sponsored products, "customers also viewed" prices, and footer text out of the output.

**An order block runs from its header line up to (but not including) the next order's header
line** (or end of document). All products, delivery lines, and action lines in that span
belong to that order.

### 6.2 Multi-item orders → one row per product

An order block may list **one or more products** under a single header (e.g. an order totalling
`$89.83` listing both "Amazon Basics 8-Pack…Batteries" and "FTSLVHI NACS to CCS…Adapter").
The page export shows **only the order-level total** — there is **no per-product price** in the
block.

- Emit **one CSV row per product** found in the order block (see §6.4 for how products are
  identified and their descriptions assembled).
- The order's **date** is copied onto every row from that order.
- The order's **total is divided evenly** across the products in that order (see §6.3).
- A single-item order therefore yields one row whose price equals the full order total.

### 6.3 Field mapping (per product row)

Let `N` = number of products in the order, `T` = the order total (from the value line).

| CSV column         | Value |
|--------------------|-------|
| `date`             | The order-placed date, converted to **ISO `YYYY-MM-DD`** (e.g. `July 11, 2026` → `2026-07-11`). Same for every row of the order. |
| `item_description` | This product's description text (see §6.4). Keep any trailing truncation `…` **as-is**; do not recover truncated text. |
| `quantity`         | `1`. |
| `unit_price`       | The order total divided evenly: `T / N`, rounded to cents (see rounding rule). Equal to `total_price` for each row. |
| `total_price`      | Same value as `unit_price` for that row. |

**Even-split rounding (exact rule):** compute in integer cents so each order's rows sum back to
the order total exactly. `cents = round(T × 100)`, `base = cents // N`, `remainder = cents − base×N`.
Assign `base+1` cents to the **first `remainder`** rows and `base` cents to the rest; convert
each back to a 2-decimal value. Use a decimal/integer method (not binary float) to avoid
rounding drift. Examples: `$89.83 / 2 → 44.92, 44.91` (sum 89.83); `$16.21 / 2 → 8.11, 8.10`;
`$141.80 / 2 → 70.90, 70.90`; single-item `$7.03 / 1 → 7.03`.

Rationale: the export exposes only an order-level total, so quantity is `1` per product row and
the spend is distributed evenly across the order's products, preserving the order total to the
cent while producing one row per item as required.

### 6.4 Product identification & description extraction

Within an order block, each product is a run of product-name text (which may **wrap across
multiple lines**), separated from the next product by that product's action/status lines.

- A product's description is the product-name run, with wrapped lines **joined into a single
  string separated by single spaces**.
- Preserve original characters within kept description lines (including unicode like `”`, `–`,
  fullwidth punctuation) and keep trailing `…` as-is.
- **Exclude** non-product "noise" lines even when adjacent — do not let them start, extend, or
  merge into a description. Match as line-leading/contained tokens (non-exhaustive):
  `Delivered`, `Your package`, `Package was`, `Ask Alexa`, `Ask Product Question`, `Return`,
  `Return window closed`, `Return or replace items`, `Return items`, `Buy it again`,
  `More options`, `Track package`, `Get product support`, `Leave seller feedback`,
  `Add a`, `Problem with order`, `Auto-delivered`, `View your Subscribe & Save`, `Share gift`,
  `Write a product`, `View order details`, `View invoice`, `View return/refund status`,
  `Why is a refund`, `When will I get my refund`, and the order header/value lines themselves.
- A **standalone small integer line** (e.g. a lone `2` or `3`) sometimes appears in the export
  (a quantity/section badge from the page); it is **not** a product and must be ignored, not
  treated as a description.
- Count `N` (for the price split) as the number of distinct product descriptions successfully
  extracted from the block. If a block has a valid header/total but **zero** extractable
  product descriptions, emit a **single** row for that order with an **empty**
  `item_description` and `unit_price = total_price = T` (the order is still a valid payment
  record; do not drop it solely for a missing description).

> Implementer note: description/product recovery is the most fragile part. Anchor products to
> their own action/status lines within the order span rather than a naive "N lines above/below
> the header," which mis-assigns wrapped text and page chrome. Validate against all provided
> samples — see §9 for exact expected row counts.

### 6.5 Refunds and credits are dropped (whole order)

Some order blocks carry a refund/credit marker (seen in samples: `Refund issued`, `Refunded`,
`A refund will appear on your original payment method`, `Your refund has been issued`). These
orders still have a normal positive header/total, but per the product decision they represent
**refunds/credits, not payment transactions we count**.

- If an order block contains any refund/credit marker (above list; match case-insensitively and
  treat the list as extensible), **drop the entire order** — emit **no rows** for it, including
  all of its products.
- This is intentional over-exclusion of an edge case: a purchase that was later refunded is
  excluded entirely.

### 6.6 Header-less / partial blocks

An export page may show a product block whose order header (`ORDER PLACED / TOTAL / ORDER #`)
fell on a **previous page** not included in the file (seen in `Your_Orders3.pdf`: a
`Delivered June 25` block with products but no header/total on the page). Because there is no
header+value pair, there is **no date and no total** — such a block is **not** a valid record
and must be **ignored** (produce no rows). Do not attempt to synthesize a total for it.

### 6.7 Other exclusions (explicit)

Shipping, tax, promotions, gift-card amounts, and any per-item price breakdown are **dropped**
(they are not present at order level in this layout and must never be synthesized). Note: a
product may itself be a gift card (e.g. "Visa Physical Gift Card $100 (plus $5.95 Purchase
Fee)") — that is a normal purchased product and **is** kept; only refunded/credited *orders*
(§6.5) are dropped.

### 6.5 Debug output

- At **debug** log level, after parsing a PDF, write to **stdout** the number of orders parsed
  from that PDF.

---

## 7. CSV output

- One CSV per successfully-parsed PDF.
- **Filename mirrors the input PDF name**: `statement.pdf` → `statement.csv` (replace the
  extension; preserve the base name exactly, case-sensitive).
- Written into `output_dir` (local or S3).
- **Header row, always present** when a CSV is written:
  `date,item_description,quantity,unit_price,total_price`
- One data row per record, columns in that exact order.
- Standard CSV quoting/escaping (e.g. Python `csv` module) so descriptions containing commas
  or quotes are safe.
- No CSV is written for a PDF that produced zero records or errored (§4, §8).

---

## 8. Error handling

For any per-PDF failure — over 32 MB, unreadable/malformed PDF, no recognized source
thumbprint, zero extractable records, or write failure — the program must:

1. Write a descriptive error **to stderr** (for the no-thumbprint case, use the exact
   `parser not found for first 10 lines:` message plus the ten lines, §5).
2. **Not** create a CSV for that PDF.
3. **Continue** to the next PDF.

Whole-run/argument failures (§2) write to stderr and exit non-zero. Per-PDF failures should
not, by themselves, make an otherwise-successful run exit non-zero (recommended: exit 0 if the
run executed; reserve non-zero for argument/environment failures). Confirm exit-code policy
with the product owner if the pipeline relies on it.

---

## 9. Acceptance criteria (validate against the provided samples)

Four real sample exports are provided as fixtures. All are single-page Safari "Your Orders"
exports. Counts below are verified against the extracted text.  The samples are located in the following
directory: `./backend/pdf2csv/data/AmazonOrderHistoryPDFs`

### General (all samples)
- Detects source as **Amazon** from the first 10 lines (thumbprint appears via "Search Amazon").
- All dates are ISO `YYYY-MM-DD` (e.g. `July 11, 2026` → `2026-07-11`, `January 1, 2026` → `2026-01-01`).
- Every row has `quantity = 1`.
- For each order, the emitted rows' `total_price` values **sum exactly to the order total**
  (even-split rounding, §6.3).
- **No rows** from the sponsored strip, "Customers who viewed…", "Similar to your past
  purchases", "Your Browsing History", the top nav, or the footer.
- Output filename mirrors input: `Your_Orders3.pdf` → `Your_Orders3.csv`, etc.
- Header row always present; standard CSV quoting for descriptions containing commas.
- At debug level, stdout reports the number of **orders parsed** (kept orders, not product rows) for each PDF.

### `1.pdf`
- **10 orders**, none refunded, none multi-item → **10 product rows**.
- Order `112-5521156-4989032` → date `2026-08-23`, `unit_price = total_price = 10.81`.

### `Your_Orders3.pdf`
- **10 orders with headers, 0 refunds → all 10 kept.**
- Two orders are **multi-item** and must split into 2 rows each with an even price split:
  - `112-9944099-3660251` ($89.83, batteries + Tesla adapter) → rows of `44.92` and `44.91`.
  - `113-0613443-6376266` ($19.03, CR2032 batteries + coffee) → rows of `9.52` and `9.51`.
- The header-less **`Delivered June 25`** block (products but no `ORDER PLACED/TOTAL/ORDER #`
  on the page) must produce **no rows** (§6.6).
- Total product rows = 10 orders + 2 extra from the two 2-item orders = **12 rows**.

### `Your_Orders5.pdf`
- **10 orders with headers, but 2 are refunds and must be dropped entirely (§6.5):**
  - `113-6506281-3975409` ($19.47, "Refund issued", SHINESTAR grill plates) → **dropped**.
  - `113-3911170-7969005` ($9.99, "Refunded", Peet's coffee) → **dropped**.
- **8 orders kept.** Multi-item orders among the kept 8 (e.g. the $92.69 order with Cedarcide +
  Mosquito Dunks + Jadaol cable; the two-product $7.72/$10.24 groupings) split into per-product
  rows with even price splits; the exact kept-order set is the 8 non-refunded headers.
- The "Visa Physical Gift Card $100 (plus $5.95 Purchase Fee)" order ($105.95) is a **kept**
  purchase (it is a product, not a refund) → its row(s) are emitted.

### `Your_Orders7.pdf`
- **9 orders with headers, 0 refunds → all 9 kept.**
- One order is **multi-item**: `112-6358312-8036217` ($16.21, Hornady BBs + Umarex CO2
  cartridges) → rows of `8.11` and `8.10`.
- Standalone badge line (`2` before the Fiber One order) must be ignored, not treated as a product.

### Framework
- A `.PDF`-extensioned file is processed; a non-`.pdf` file is ignored; scan is non-recursive.
- A PDF whose first 10 lines contain no known thumbprint yields the exact
  `parser not found for first 10 lines:` message (plus the ten lines) on stderr and no CSV.
- A > 32 MB PDF, an unreadable/malformed PDF, and a PDF yielding zero records each produce a
  stderr error, no CSV, and do not stop processing of the other PDFs.

---

## 10. Design constraints

- **Language:** Python. Pin to the version in the repo's `.python-version`.
- This python program should be built in a UV environment like the other python programs such as `./backend/PIICalculator`.  Please
follow the same folder structure: src, tests.
- **CLI:** `argparse`.
- **Text extraction:** native only, no OCR.
- **Architecture: modular, SOLID.** Concretely:
  - **Single responsibility / separation of concerns** for: (a) path/storage access (local vs S3 behind one interface), (b) PDF text extraction, (c) source detection, (d) per-source parsing, (e) CSV writing, (f) CLI orchestration.
  - **Open/closed:** adding a new source = add a new parser class implementing a common parser interface and register it with the detector/dispatcher; **no edits** to existing framework or other parsers.
  - **Liskov / interface segregation:** all parsers share one small interface (e.g. `matches(first_10_lines) -> bool` and `parse(lines) -> list[Record]`, or a registry keyed by detected source). Storage access shares one small interface (`list_pdfs`, `read_bytes`, `write_text`) with local and S3 implementations.
  - **Dependency inversion:** orchestration depends on the storage and parser **abstractions**, not on boto3/pdf-library concretions; those are injected.
- **Libraries:** no restriction on which libraries, but **all dependencies must run on ARM** architecture. Choose an actively-maintained native-text PDF extraction library that works on ARM.
- **TDD workflow (required):** for every unit of behavior, **write the failing test first, then the product code**. Cover at minimum: argument validation (both paths, local + S3, failure messages); directory scan (extension case-insensitivity, filename case-sensitivity, non-recursion); size limit; source detection (Amazon hit, no-match message); Amazon parsing (order count, ISO date conversion, total mapping, quantity=1, unit_price=total, description joining + truncation preserved, chrome/footer exclusion, refund/credit exclusion); CSV output (filename mirroring, header, quoting); per-PDF error isolation (one bad PDF doesn't stop the rest, no CSV on failure). Use the provided sample PDF(s) as fixtures for parser tests.

---

## 11. Out of scope (this story)

- Bank and credit-card parsers (detector must be *ready* for them; do not implement).
- The Amazon "request your order history" report (that is a CSV/ZIP download, not a PDF).
- OCR / scanned PDFs.
- Recursive directory traversal.
- Downstream pipeline steps (normalization, anonymization, categorization, PII calculation).