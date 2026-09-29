# Story — Ticket Minting Function (`mint_ticket`)

## Context for the implementing agent
This function is the first step of the PII application's auth flow. It mints a
session credential: a **ticket ID** (public, a ULID) paired with a **secret**
(a bearer credential). Only a hash of the secret is persisted. The raw secret is
returned to the caller exactly once and never stored.

The function will later be wrapped as an AWS Lambda, but for now it must be
callable as a plain Python function and exercisable from a CLI. Write it so the
core logic has no dependency on Lambda or API Gateway request/response shapes.

Language: Python 3.12 (matching project pyproject.toml and standard AWS Lambda runtimes).
Prefer standard library; `boto3` client for DynamoDB; `python-ulid` (or equivalent) for ULID generation.

---

## User story
**As** the auth layer of the PII application,
**I want** a function that mints a ticket ID and secret, persists a hash of the
secret to DynamoDB, and returns the ticket ID and raw secret,
**so that** subsequent requests can be authorized by looking up the ticket and
verifying the presented secret against the stored hash.

---

## Interface (implement exactly)

```python
def mint_ticket(
    table_name: str,
    ttl_seconds: int = 86_400,
    dynamodb_client=None,  # inject boto3.client("dynamodb") for testing; defaults to boto3.client("dynamodb")
) -> dict:
    """
    Mint a ticket and secret, persist the secret hash, and return the credential.

    Returns:
        {
            "ticket_id": str,   # ULID, safe to log and expose
            "secret":    str,   # raw bearer secret, base64url without padding, returned ONCE
        }
    """
```

CLI wrapper (`mint_ticket.cli` / console script `ticket-issuer` — thin, no business logic of its own):

```bash
python -m mint_ticket.cli --table-name <TABLE_NAME> [--ttl-seconds 86400]
# or via entrypoint:
ticket-issuer --table-name <TABLE_NAME> [--ttl-seconds 86400]
```

- Accepts `--table-name` flag, falling back to environment variable `TICKETS_TABLE_NAME` (or `DYNAMODB_TABLE_NAME`) if 
`--table-name` is omitted.
- Optional `--ttl-seconds` defaults to `86400`.
- On success: prints the returned `ticket_id` and `secret` as JSON to stdout with exit code 0.
- On error (e.g., missing table configuration, DynamoDB failure, collision): writes a structured error message to 
stderr and exits with a non-zero exit code (e.g., 1) rather than dumping an unhandled stack trace.

---

## Behaviour (deterministic requirements)

1. **Ticket ID** — generate a ULID; use its canonical 26-char string form.
2. **Secret** — generate 32 bytes from `secrets.token_bytes(32)` (a CSPRNG);
   encode as base64url without padding (`base64.urlsafe_b64encode(...).rstrip(b'=').decode('ascii')`).
3. **Hash** — `hashlib.sha256(raw_secret_bytes).hexdigest()`. Store the hash,
   never the raw secret. (Plain SHA-256 is correct here: the secret already has
   256 bits of entropy, so a slow password hash like bcrypt/Argon adds latency
   for no security gain.)
4. **Persist** — write one DynamoDB item via `dynamodb_client.put_item(...)`:
   - `TableName`: `table_name`
   - `Item`:
     - `ticket_id`: `{"S": ticket_id}` (partition key)
     - `secret_hash`: `{"S": secret_hash}`
     - `job_status`: `{"S": "issued"}`
     - `expires_at`: `{"N": str(int(now + ttl_seconds))}` (epoch seconds as DynamoDB number attribute)
     - `created_at`: `{"S": now_iso_utc}` (ISO 8601 UTC timestamp)
   - `ConditionExpression`: `"attribute_not_exists(ticket_id)"` so a ULID
     collision fails loudly rather than overwriting.
5. **Return** — the ticket ID and the raw (base64url) secret. The raw secret must
   not be logged, printed to logs, or persisted anywhere but the caller's return.

---

## Acceptance criteria

- Calling `mint_ticket` returns a dict with non-empty `ticket_id` and `secret`.
- Exactly one DynamoDB item is written per call via `dynamodb_client.put_item`, keyed by the returned ticket ID.
- The stored item contains `secret_hash` and does **not** contain the raw secret.
- `sha256(base64url_decode(returned_secret)) == stored secret_hash`.
- `expires_at` equals now + `ttl_seconds` (± small clock delta), as epoch seconds in a numeric attribute.
- Two calls never return the same `ticket_id` or the same `secret`.
- The secret is generated with `secrets`/`token_bytes` (a CSPRNG), never `random`.
- Raw secret never appears in log output.
- The CLI prints valid JSON with `ticket_id` and `secret` on stdout upon success.
- The CLI supports `--table-name` and falls back to `TICKETS_TABLE_NAME` environment variable; exits non-zero with 
stderr output on error.
- Core logic is unit-testable with an injected/mocked DynamoDB client (`boto3.client("dynamodb")`) — no live AWS call 
required in tests.
- Unit tests for `mint_ticket` and `cli` provide coverage of at least 80%.

---

## Explicitly out of scope
- The authorizer/verification path (looking up a ticket and comparing a presented
  secret) is a **separate** function and a separate story.
- Lambda handler wrapping, API Gateway wiring, and IAM roles are separate stories.
- JWT signing — not used in this design.

---

## Notes / rationale (for the agent's judgement, not to reimplement)
- The ULID is deliberately **not** the secret: a ULID embeds a timestamp and is
  sortable/predictable, so it must not be used as a bearer credential. It is the
  public identifier only.
- Comparison of secrets on the verification side must be constant-time
  (`hmac.compare_digest`) — note it here so the sibling story inherits it.

## DynamoDB testing requirements

Unit tests for ticket minting must validate DynamoDB behavior without making live AWS calls.

### Test setup

- Tests must inject a fake or mocked DynamoDB client into `mint_ticket`.
- Tests must not require AWS credentials.
- Tests must not call a real DynamoDB table.
- The fake or mocked client must capture the arguments passed to `put_item`.

### Required DynamoDB assertions

The tests must verify that each successful call to `mint_ticket` performs exactly one DynamoDB write.

Assert that the `put_item` call includes:

- `TableName`: The configured table name.
- `Item`:
  - `ticket_id`: `{"S": ticket_id}` matching the returned `ticket_id`.
  - `secret_hash`: `{"S": secret_hash}` matching SHA-256 of the raw secret.
  - `job_status`: `{"S": "issued"}`.
  - `expires_at`: `{"N": ...}` represented as epoch seconds string.
  - `created_at`: `{"S": ...}` represented as an ISO 8601 UTC timestamp string.
- `ConditionExpression`: `"attribute_not_exists(ticket_id)"`.

### Secret persistence assertions

The tests must verify that the raw secret is never persisted.

Assert that:

- The DynamoDB item does not contain a `secret` attribute.
- The DynamoDB item does not contain the returned raw secret under any other attribute name.
- The stored `secret_hash["S"]` equals: `hashlib.sha256(base64url_decode(returned_secret)).hexdigest()`.

The returned secret is base64url encoded without padding, so the test may need to restore padding before decoding.

### TTL assertions

The tests must verify that `expires_at` is calculated from the current time plus `ttl_seconds`.

Use a small `ttl_seconds` value, such as `60`, and capture time immediately before and after calling `mint_ticket`.

Assert that: `before + ttl_seconds <= int(expires_at["N"]) <= after + ttl_seconds`

Allow only a small clock delta caused by test execution time.

### Conditional write failure

The tests must include a failure case where the injected DynamoDB client raises an exception from `put_item`, 
such as a conditional write failure (`ClientError` / `ConditionalCheckFailedException`).

Assert that:

- `mint_ticket` does not swallow the exception.
- No successful ticket response is returned when the DynamoDB write fails.

### Uniqueness and write consistency

The tests must call `mint_ticket` at least twice and verify that:

- The returned `ticket_id` values are different.
- The returned `secret` values are different.
- Each call produces exactly one DynamoDB write.
- Each written item is keyed by the corresponding returned `ticket_id`.

### Scope

These are unit tests only.

Do not require:

- DynamoDB Local.
- A deployed AWS DynamoDB table.
- AWS credentials.
- Network access.

Optional integration tests against DynamoDB Local or a sandbox AWS table may be 
added separately, but they must not be required for the normal unit test suite.


