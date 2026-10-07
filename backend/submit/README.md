# Submit Service

The Submit Lambda is the front door for uploading spending statement PDFs to the PII pipeline.
It validates a batch of upload file descriptors, calls `mint_ticket` to generate session credentials,
records upload expectations in DynamoDB, and returns presigned S3 PUT URLs for direct client uploads.
