# Story: UploadWatcher Lambda Handler (upload-complete trigger)

# Summary
As an application developer,
I want a Lambda that watches S3 uploads and starts the pipeline once all of a
ticket's PDFs have landed,
so that the Step Functions execution runs against the complete set of uploaded
files and never races a partial upload.

This is the second half of the batch-submit design. Submit (separate story:
`story-submit-handler.md`) mints the ticket, records `expectedFileCount`, and
returns presigned URLs — but does **not** start the pipeline. The UploadWatcher
is what starts it, after the uploads are confirmed present.

# Background
Submit hands the browser N presigned URLs and returns. Those N PUTs go directly to
S3 and never touch the API, so nothing on the server side knows when the batch is
complete — unless something watches S3 itself. That watcher is this Lambda.

It is invoked **once per uploaded object**, not once per batch: each completed PUT
emits an `ObjectCreated` event, and each event is a separate invocation. The
invocations do not coordinate with each other directly; the shared DynamoDB ticket
row is the coordination point. Whichever invocation observes the full set is the
one that starts the pipeline.

The trigger is scoped to the bucket/prefix, not to a ticket: every `ObjectCreated`
under `uploads/` invokes this one Lambda regardless of ticket. The handler derives
the `ticketId` from the object key and operates on that row. One Lambda serves all
tickets.

# Handler (count + conditionally start)

## Event Contract
S3 event notification (the `Records` array shape). Each record carries
`s3.bucket.name` and `s3.object.key`. The key is URL-encoded — unquote it before
parsing. Keys look like `uploads/<ticketId>/<filename>.pdf`.

- A record whose key does not match `uploads/<ticketId>/...` is ignored.
- Multiple records in one event are each processed.

## Handler flow
1. For each record, unquote the key and derive `ticketId` from
   `uploads/<ticketId>/...`.
2. Count current `.pdf` objects under `uploads/<ticketId>/` (ListObjectsV2).
3. Read the ticket row; compare count to `expectedFileCount`.
4. If all present and `job_status == "AWAITING_UPLOAD"`:
   - Conditionally flip `job_status` to `PROCESSING`
     (`ConditionExpression` on the old value) — this makes the start **idempotent**
     even if several `ObjectCreated` events fire near-simultaneously. Only one
     invocation wins the write.
   - Call Step Functions `StartExecution`, `name = ticketId`,
     input `{ "input-s3-uri": "s3://<input-bucket>/uploads/<ticketId>" }`
     (matches the Normalizer event contract).
   - Treat `ExecutionAlreadyExists` as success (belt-and-suspenders alongside the
     conditional flip).
5. If not yet complete, do nothing (wait for later events).

Module: `backend/upload-watcher/src/upload_watcher/lambda_handler.py`
Entry: `upload_watcher.lambda_handler.handler` | Python 3.12, arm64 | 256 MB | 30 s.
Clients injectable via module-level factory for tests.

Note: the directory is kebab-case (`backend/upload-watcher`) while the Python
package and handler path use underscores (`upload_watcher.lambda_handler.handler`).

# Error handling
- Idempotent by design: a redelivered or duplicate event must not start a second
  execution (guarded by the conditional status flip + ticket-named execution).
- A malformed or non-matching key is skipped, not fatal.
- Downstream failures (ListObjectsV2, DynamoDB, StartExecution) surface as errors
  so the invocation can be retried by the event source; retries are safe because
  the start is idempotent.
- Never log the raw secret or any presigned URL. The `ticketId` is public and may
  be logged for correlation.

# Out of scope
- Terraform for the Lambda, its IAM role, and the S3 event/EventBridge wiring
  (invoke permission, bucket notification, prefix filter).
- `mint_ticket`, submit, the state machine definition, the /status authorizer.
- The finalize/timeout mitigation for incomplete uploads (see Open item).

# Packaging
- ZIP deployment package with dependencies (no container).
- Python 3.12, arm64, uv for dependency management.
- Build script `backend/upload-watcher/build_n_package_lambda.sh`, mirroring
  `backend/pdf2csv/build_n_package_lambda.sh`:
  1. Clean/create the build_lambda directory.
  2. In a `public.ecr.aws/lambda/python:3.12` Docker container
     (`--platform linux/arm64`), install uv and run
     `uv pip install . --target build_lambda`.
  3. Remove tests and __pycache__; strip .so files.
  4. Zip to `upload-watcher.zip`; print package name, SHA-256 digest, handler
     (`upload_watcher.lambda_handler.handler`), runtime, and target.

# Documentation
Add `backend/upload-watcher/upload_watcher_deployment.md`, mirroring the structure
of `backend/pdf2csv/Normalizer_deployment.md`:
- Overview
- Lambda Deployment: Prerequisites (Docker, Python 3.12, uv, zip), Building the
  Package, Lambda Configuration (arm64, Python 3.12, handler, 256 MB, 30 s;
  environment variables: input bucket name, tickets table name, state machine ARN),
  Event Contract (S3 `ObjectCreated` notification shape), Lambda Success Response,
  Direct Lambda Testing (local Python snippet with a sample S3 event +
  `aws lambda invoke` example)
- Testing methodology
- S3 / Step Functions: note that the bucket notification and the state machine are
  owned by the infra repo; show the expected S3 event shape and how the handler
  starts the execution once wired, mirroring the Normalizer doc

# Acceptance criteria
- On an `ObjectCreated` event, the handler derives the correct `ticketId` from the
  (URL-decoded) key and counts PDFs under `uploads/<ticketId>/`.
- The pipeline starts exactly once, only after all expected PDFs are present,
  named with the ticket ID; redelivered or concurrent S3 events do not double-start.
- The status flip from `AWAITING_UPLOAD` to `PROCESSING` is conditional; a losing
  concurrent invocation does not start a second execution.
- `ExecutionAlreadyExists` is treated as success.
- An event whose count is short results in no state change and no execution.
- Non-matching keys are skipped without error.
- Secret and presigned URLs never appear in logs.
- The handler is unit-testable with injected/faked S3, DynamoDB, and Step Functions
  clients — including the concurrent-completion case.
- The Lambda package is a ZIP built for Python 3.12 / arm64 via
  `build_n_package_lambda.sh` using uv; production dependencies install
  reproducibly.
- `upload_watcher_deployment.md` documents configuration (256 MB, 30 s, the three
  environment variables), the S3 event contract, direct testing, and validation.
- New unit tests cover count-short, count-complete, concurrent-completion, and
  non-matching-key cases with AWS clients mocked; existing tests pass.

# Open item flagged
- Count-based completion assumes the user uploads exactly the declared set. If a
  file's PUT never succeeds, the count never reaches `expectedFileCount` and the
  pipeline never starts. Mitigations for a later story: a client finalize call, or
  a timeout sweeper that fails or notifies stuck `AWAITING_UPLOAD` tickets after
  their TTL window.