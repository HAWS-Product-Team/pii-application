"""AWS Lambda handler for the CSV merge step.

Orchestrates downloading CSV files from S3, merging them locally using
the merge core engine, and uploading the consolidated CSV to S3.

Expected event:
    {
        "input-s3-uri": "s3://bucket/123456789/upload",
        "output-s3-uri": "s3://bucket/123456789/purchase_data.csv"
    }

Success response:
    {
        "ticket": "123456789",
        "status": "SUCCEEDED",
        "output-s3-uri": "s3://bucket/123456789/purchase_data.csv"
    }
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from urllib.parse import urlparse

from .merger import MergeError, merge_csv_files
from .storage import LocalStorage

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

DEFAULT_EPHEMERAL_STORAGE_LIMIT_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB
EPHEMERAL_STORAGE_BUDGET_FRACTION = 0.8  # 80%
DEFAULT_MAX_INPUT_BYTES = int(
    DEFAULT_EPHEMERAL_STORAGE_LIMIT_BYTES * EPHEMERAL_STORAGE_BUDGET_FRACTION
)


def get_s3_client():
    """Module-level factory to instantiate boto3 S3 client."""
    import boto3

    return boto3.client("s3")


def _parse_s3_uri(uri: str, field_name: str) -> tuple[str, str]:
    """Parse and validate an S3 URI, returning (bucket, key)."""
    if not isinstance(uri, str) or not uri.startswith("s3://"):
        raise MergeError(
            f"Malformed S3 URI for '{field_name}': '{uri}'. URI must start with s3://"
        )

    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    if not bucket:
        raise MergeError(
            f"Malformed S3 URI for '{field_name}': '{uri}'. Missing bucket name."
        )
    if not key:
        raise MergeError(
            f"Malformed S3 URI for '{field_name}': '{uri}'. Missing key path."
        )

    return bucket, key


def _extract_ticket(input_uri: str, input_key: str) -> str:
    """Extract and validate the numeric ticket number from the input S3 path."""
    segments = [s for s in input_key.strip("/").split("/") if s]
    if not segments:
        raise MergeError(
            f"Missing ticket number in input S3 URI '{input_uri}'"
        )

    ticket = segments[0]
    if not ticket.isdigit():
        raise MergeError(
            f"Invalid ticket number '{ticket}' in input S3 URI '{input_uri}': ticket must be numeric"
        )

    return ticket


def handler(
    event: dict,
    context: object = None,
    s3_client: object = None,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
) -> dict:
    """Merge CSV files from S3 and upload the consolidated output to S3.

    Args:
        event: Lambda invocation event dictionary.
        context: Lambda context object (unused).
        s3_client: Injectable S3 client for unit testing.
        max_input_bytes: Maximum total input size in bytes allowed before download.

    Returns:
        Dict containing ticket, status ("SUCCEEDED"), and output-s3-uri.

    Raises:
        MergeError: On event validation error, missing CSVs, ephemeral storage budget exceeded,
                    S3 read/write errors, or merge conversion failures.
    """
    if not isinstance(event, dict):
        raise MergeError("Event must be a dictionary")

    input_uri = event.get("input-s3-uri")
    if not input_uri:
        raise MergeError("Missing required event field: 'input-s3-uri'")

    output_uri = event.get("output-s3-uri")
    if not output_uri:
        raise MergeError("Missing required event field: 'output-s3-uri'")

    in_bucket, in_key = _parse_s3_uri(input_uri, "input-s3-uri")
    out_bucket, out_key = _parse_s3_uri(output_uri, "output-s3-uri")

    if output_uri.endswith("/") or not out_key:
        raise MergeError(
            f"Malformed output S3 URI: '{output_uri}'. Must specify a destination file path."
        )

    ticket = _extract_ticket(input_uri, in_key)

    logger.info(
        "Starting merge orchestration for ticket=%s input=%s output=%s",
        ticket,
        input_uri,
        output_uri,
    )

    if s3_client is None:
        try:
            s3_client = get_s3_client()
        except Exception as exc:
            raise MergeError(f"Failed to initialize S3 client: {exc}") from exc

    # 1. List all objects under the input prefix
    prefix = in_key.rstrip("/") + "/"
    csv_objects: list[tuple[str, int]] = []

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=in_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                if key.lower().endswith(".csv"):
                    size = obj.get("Size", 0)
                    csv_objects.append((key, size))
    except Exception as exc:
        raise MergeError(
            f"S3 read failure listing objects at '{input_uri}' for ticket '{ticket}': {exc}"
        ) from exc

    if not csv_objects:
        raise MergeError(
            f"No CSVs found at input path '{input_uri}' for ticket '{ticket}'"
        )

    # 2. Check total input size budget
    total_input_size = sum(size for _, size in csv_objects)
    if total_input_size > max_input_bytes:
        raise MergeError(
            f"Total input size ({total_input_size} bytes) exceeds ephemeral storage budget "
            f"({max_input_bytes} bytes) for ticket '{ticket}' at '{input_uri}'"
        )

    logger.info(
        "Found %d CSV file(s) (%d bytes total) for ticket=%s",
        len(csv_objects),
        total_input_size,
        ticket,
    )

    # 3. Download CSVs to a temporary directory under /tmp, run merge, and upload
    tmp_dir = tempfile.mkdtemp(prefix=f"merge_{ticket}_", dir="/tmp")
    tmp_in_dir = os.path.join(tmp_dir, "input")
    os.makedirs(tmp_in_dir, exist_ok=True)
    tmp_out_file = os.path.join(tmp_dir, "purchase_data.csv")

    try:
        for idx, (key, _size) in enumerate(csv_objects):
            base_filename = os.path.basename(key)
            local_path = os.path.join(tmp_in_dir, base_filename)
            if os.path.exists(local_path):
                local_path = os.path.join(tmp_in_dir, f"{idx}_{base_filename}")

            try:
                s3_client.download_file(in_bucket, key, local_path)
            except Exception as exc:
                raise MergeError(
                    f"S3 read failure downloading '{key}' from bucket '{in_bucket}' for ticket '{ticket}': {exc}"
                ) from exc

        # 4. Invoke the merge app conversion over the local directory
        try:
            result = merge_csv_files(
                storage=LocalStorage(),
                input_location=tmp_in_dir,
                output_path=tmp_out_file,
            )
        except MergeError as exc:
            raise MergeError(f"Conversion failure for ticket '{ticket}': {exc}") from exc
        except Exception as exc:
            raise MergeError(
                f"Unexpected conversion failure for ticket '{ticket}': {exc}"
            ) from exc

        if not os.path.isfile(tmp_out_file) or os.path.getsize(tmp_out_file) == 0:
            raise MergeError(
                f"Merge conversion produced no CSV output file for ticket '{ticket}'"
            )

        # 5. Upload the merged output CSV to S3
        try:
            s3_client.upload_file(tmp_out_file, out_bucket, out_key)
        except Exception as exc:
            raise MergeError(
                f"S3 write failure uploading to '{output_uri}' for ticket '{ticket}': {exc}"
            ) from exc

        logger.info(
            "Successfully merged %d files (%d total rows) for ticket=%s and uploaded to %s",
            result.file_count,
            result.total_rows,
            ticket,
            output_uri,
        )

        return {
            "ticket": ticket,
            "status": "SUCCEEDED",
            "output-s3-uri": output_uri,
        }

    finally:
        # Clean up temporary directory unconditionally
        shutil.rmtree(tmp_dir, ignore_errors=True)


# Backwards compatibility alias
lambda_handler = handler
