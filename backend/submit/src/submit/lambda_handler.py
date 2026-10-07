"""
Submit Lambda Handler for batch upload initialization.

Validates the uploaded file list, calls mint_ticket to create ticket credentials,
records expected_file_count and AWAITING_UPLOAD status in DynamoDB, and generates
presigned S3 PUT URLs for direct client uploads.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
from typing import Any

import boto3
from mint_ticket.issuer import mint_ticket

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Defaults
DEFAULT_MAX_FILES = 20
DEFAULT_MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB
DEFAULT_PRESIGNED_EXPIRY_SECONDS = 900
DEFAULT_TICKET_TTL_SECONDS = 86_400
MIN_FILE_SIZE_BYTES = 1024 * 1024  # 1 MB (1,048,576 bytes)
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB (15,728,640 bytes)

FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")

CORS_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def get_dynamodb_client() -> Any:
    """Factory for DynamoDB low-level client."""
    return boto3.client("dynamodb")


def get_s3_client() -> Any:
    """Factory for S3 client."""
    return boto3.client("s3")


def error_response(status_code: int, message: str) -> dict[str, Any]:
    """Build an API Gateway proxy error response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def parse_event_body(event: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """
    Extract the JSON payload from API Gateway proxy event or direct event.

    Returns:
        (payload, error_message)
    """
    if "body" in event:
        raw_body = event.get("body")
        if raw_body is None:
            return None, "Missing request body"

        if event.get("isBase64Encoded"):
            try:
                raw_body = base64.b64decode(raw_body).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                return None, "Invalid base64-encoded body"

        if isinstance(raw_body, str):
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                return None, "Invalid JSON in request body"
        elif isinstance(raw_body, dict):
            payload = raw_body
        else:
            return None, "Invalid request body format"
    elif isinstance(event, dict) and "files" in event:
        payload = event
    else:
        return None, "Invalid request payload: 'files' is required"

    if not isinstance(payload, dict):
        return None, "Payload must be a JSON object"

    return payload, None


def validate_files(
    files: Any,
    max_files: int,
    max_total_bytes: int,
) -> str | None:
    """
    Validate batch files array and individual file specifications.

    Returns:
        Error message string if invalid, or None if valid.
    """
    if not isinstance(files, list):
        return "'files' field must be an array"

    if len(files) == 0:
        return "Batch 'files' list cannot be empty"

    if len(files) > max_files:
        return f"Batch file count ({len(files)}) exceeds maximum allowed ({max_files})"

    total_bytes = 0
    seen_filenames: set[str] = set()

    for idx, item in enumerate(files):
        if not isinstance(item, dict):
            return f"Item at index {idx} in 'files' must be a JSON object"

        # Validate filename
        filename = item.get("filename")
        if filename is None:
            return f"Missing required 'filename' at index {idx}"
        if not isinstance(filename, str) or not filename.strip():
            return f"Invalid 'filename' at index {idx}: must be a non-empty string"

        # Reject path traversals and directory separators
        if "/" in filename or "\\" in filename or ".." in filename:
            return f"Invalid 'filename' '{filename}': directory separators and path traversal are not allowed"

        # Must end in .pdf (case-insensitive)
        if not filename.lower().endswith(".pdf"):
            return f"Invalid 'filename' '{filename}': file must have a .pdf extension"

        # Must contain non-whitespace characters before .pdf
        base_part = filename[:-4].strip()
        if not base_part:
            return f"Invalid 'filename' '{filename}': filename must contain characters before extension"

        # Safe characters check
        if not FILENAME_PATTERN.match(filename):
            return f"Invalid 'filename' '{filename}': only alphanumeric characters, dots, dashes, and underscores are allowed"

        # Duplicate check (case-insensitive)
        lower_name = filename.lower()
        if lower_name in seen_filenames:
            return f"Duplicate filename in batch: '{filename}'"
        seen_filenames.add(lower_name)

        # Validate fileSizeBytes
        size = item.get("fileSizeBytes")
        if size is None:
            return f"Missing required 'fileSizeBytes' for file '{filename}'"
        if isinstance(size, bool) or not isinstance(size, int):
            return f"Invalid 'fileSizeBytes' for file '{filename}': must be an integer"

        if size < MIN_FILE_SIZE_BYTES:
            return (
                f"File '{filename}' size ({size} bytes) is below minimum allowed "
                f"({MIN_FILE_SIZE_BYTES} bytes / 1 MB)"
            )
        if size > MAX_FILE_SIZE_BYTES:
            return (
                f"File '{filename}' size ({size} bytes) exceeds maximum allowed "
                f"({MAX_FILE_SIZE_BYTES} bytes / 15 MB)"
            )

        total_bytes += size

    if total_bytes > max_total_bytes:
        return (
            f"Batch total size ({total_bytes} bytes) exceeds maximum allowed "
            f"({max_total_bytes} bytes)"
        )

    return None


def handler(
    event: dict[str, Any],
    context: Any = None,
    dynamodb_client: Any = None,
    s3_client: Any = None,
) -> dict[str, Any]:
    """
    AWS Lambda entrypoint for submitting batch uploads.

    Coordinates minting ticket credentials, updating DynamoDB status,
    and generating presigned S3 PUT URLs.
    """
    # Handle CORS preflight if invoked directly
    http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get(
        "method"
    )
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": "",
        }

    # Load environment variables
    table_name = os.environ.get("TICKETS_TABLE_NAME")
    bucket_name = os.environ.get("UPLOADS_BUCKET_NAME")

    if not table_name:
        logger.error("Configuration error: TICKETS_TABLE_NAME environment variable is not set")
        return error_response(500, "Internal configuration error")

    if not bucket_name:
        logger.error("Configuration error: UPLOADS_BUCKET_NAME environment variable is not set")
        return error_response(500, "Internal configuration error")

    try:
        max_files = int(os.environ.get("MAX_FILES", DEFAULT_MAX_FILES))
    except ValueError:
        max_files = DEFAULT_MAX_FILES

    try:
        max_total_bytes = int(os.environ.get("MAX_TOTAL_BYTES", DEFAULT_MAX_TOTAL_BYTES))
    except ValueError:
        max_total_bytes = DEFAULT_MAX_TOTAL_BYTES

    try:
        presigned_expiry_seconds = int(
            os.environ.get("PRESIGNED_EXPIRY_SECONDS", DEFAULT_PRESIGNED_EXPIRY_SECONDS)
        )
    except ValueError:
        presigned_expiry_seconds = DEFAULT_PRESIGNED_EXPIRY_SECONDS

    try:
        ticket_ttl_seconds = int(os.environ.get("TICKET_TTL_SECONDS", DEFAULT_TICKET_TTL_SECONDS))
    except ValueError:
        ticket_ttl_seconds = DEFAULT_TICKET_TTL_SECONDS

    # 1. Parse request body
    payload, parse_err = parse_event_body(event)
    if parse_err is not None or payload is None:
        return error_response(400, parse_err or "Invalid request")

    # 2. Validate batch
    files = payload.get("files")
    val_err = validate_files(files, max_files=max_files, max_total_bytes=max_total_bytes)
    if val_err is not None:
        return error_response(400, val_err)

    # Resolve AWS clients
    if dynamodb_client is None:
        dynamodb_client = get_dynamodb_client()
    if s3_client is None:
        s3_client = get_s3_client()

    # 3. Mint ticket
    try:
        credential = mint_ticket(
            table_name=table_name,
            ttl_seconds=ticket_ttl_seconds,
            dynamodb_client=dynamodb_client,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to mint ticket: %s", str(e))
        return error_response(500, "Failed to create ticket")

    ticket_id = credential["ticket_id"]
    secret = credential["secret"]

    # 4. Follow-up DynamoDB UpdateItem
    try:
        dynamodb_client.update_item(
            TableName=table_name,
            Key={"ticket_id": {"S": ticket_id}},
            UpdateExpression="SET #status = :new_status, #count = :count",
            ExpressionAttributeNames={
                "#status": "job_status",
                "#count": "expected_file_count",
            },
            ExpressionAttributeValues={
                ":new_status": {"S": "AWAITING_UPLOAD"},
                ":count": {"N": str(len(files))},
            },
            ConditionExpression="attribute_exists(ticket_id)",
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to update ticket status for ticket_id=%s: %s", ticket_id, str(e))
        return error_response(500, "Failed to record ticket expectations")

    # 5. Generate Presigned PUT URLs
    uploads = []
    try:
        for file_info in files:
            filename = file_info["filename"]
            key = f"uploads/{ticket_id}/{filename}"
            upload_url = s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": bucket_name,
                    "Key": key,
                    "ContentType": "application/pdf",
                },
                ExpiresIn=presigned_expiry_seconds,
            )
            uploads.append(
                {
                    "filename": filename,
                    "key": key,
                    "uploadUrl": upload_url,
                }
            )
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to generate presigned URLs for ticket_id=%s: %s", ticket_id, str(e))
        return error_response(500, "Failed to generate upload URLs")

    # 6. Return success proxy response
    response_body = {
        "ticketId": ticket_id,
        "secret": secret,
        "uploadPrefix": f"uploads/{ticket_id}/",
        "uploads": uploads,
        "expectedFileCount": len(files),
        "expiresInSeconds": presigned_expiry_seconds,
    }

    logger.info(
        "Successfully created upload batch for ticket_id=%s, file_count=%d", ticket_id, len(files)
    )

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(response_body),
    }
