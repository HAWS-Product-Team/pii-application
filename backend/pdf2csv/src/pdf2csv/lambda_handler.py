"""AWS Lambda handler for pdf2csv (Normalizer stage in PII Data Pipeline)."""

import logging
import os
import shutil
import tempfile
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from pdf2csv.converter import process_input

logger = logging.getLogger("pdf2csv.lambda_handler")

DEFAULT_EPHEMERAL_STORAGE_LIMIT_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB
DEFAULT_EPHEMERAL_STORAGE_BUDGET = int(DEFAULT_EPHEMERAL_STORAGE_LIMIT_BYTES * 0.8)  # 4 GiB (80%)


class Pdf2CsvError(Exception):
    """Base exception for PDF-to-CSV Lambda processing errors."""


# Alias for case-insensitivity consistency
Pdf2csvError = Pdf2CsvError


def get_s3_client(s3_client=None):
    """Factory for creating or injecting an S3 client."""
    if s3_client is not None:
        return s3_client
    return boto3.client("s3")


def parse_and_validate_event(event: dict) -> tuple[str, str, str, str]:
    """Validate incoming event and extract S3 location details.

    Args:
        event: Lambda event payload.

    Returns:
        tuple: (input_s3_uri, bucket, prefix, ticket)

    Raises:
        Pdf2CsvError: If event schema or S3 URI is invalid.
    """
    if not isinstance(event, dict):
        raise Pdf2CsvError("Invalid event: event must be a JSON dictionary")

    if "input-s3-uri" not in event:
        raise Pdf2CsvError("Missing required field 'input-s3-uri' in event")

    input_s3_uri = event["input-s3-uri"]
    if not isinstance(input_s3_uri, str) or not input_s3_uri.strip():
        raise Pdf2CsvError("Field 'input-s3-uri' must be a non-empty string")

    input_s3_uri = input_s3_uri.strip()
    if not input_s3_uri.startswith("s3://"):
        raise Pdf2CsvError(f"Malformed S3 URI: '{input_s3_uri}' does not start with 's3://'")

    parsed = urlparse(input_s3_uri)
    bucket = parsed.netloc
    if not bucket:
        raise Pdf2CsvError(f"Malformed S3 URI: '{input_s3_uri}' is missing bucket name")

    path = parsed.path.lstrip("/")
    if not path:
        raise Pdf2CsvError(f"Malformed S3 URI: '{input_s3_uri}' is missing object key/prefix")

    segments = [s for s in path.split("/") if s]
    if not segments:
        raise Pdf2CsvError(f"Malformed S3 URI: '{input_s3_uri}' is missing path segments")

    ticket = segments[0]
    if not ticket.isdigit():
        raise Pdf2CsvError(
            f"Missing or invalid ticket number in S3 URI '{input_s3_uri}': "
            f"first path segment '{ticket}' must be numeric"
        )

    prefix = path
    return input_s3_uri, bucket, prefix, ticket


def list_pdf_objects(s3_client, bucket: str, prefix: str, ticket: str) -> list[dict]:
    """List all PDF objects under the given S3 bucket and prefix.

    Args:
        s3_client: Boto3 S3 client.
        bucket: S3 bucket name.
        prefix: S3 key prefix.
        ticket: Ticket identifier for error context.

    Returns:
        List of matching S3 object summaries containing 'Key' and 'Size'.

    Raises:
        Pdf2CsvError: If S3 listing fails.
    """
    try:
        pdf_objects = []
        if hasattr(s3_client, "get_paginator"):
            try:
                paginator = s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        key = obj.get("Key", "")
                        if key.lower().endswith(".pdf"):
                            pdf_objects.append(obj)
            except (ClientError, BotoCoreError) as e:
                raise Pdf2CsvError(
                    f"Ticket {ticket}: S3 read failure listing objects under 's3://{bucket}/{prefix}': {e}"
                ) from e
            except Exception as e:
                # If mock get_paginator is not implemented, fallback to list_objects_v2
                if hasattr(s3_client, "list_objects_v2"):
                    resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
                    for obj in resp.get("Contents", []):
                        key = obj.get("Key", "")
                        if key.lower().endswith(".pdf"):
                            pdf_objects.append(obj)
                else:
                    raise Pdf2CsvError(
                        f"Ticket {ticket}: S3 read failure listing objects under 's3://{bucket}/{prefix}': {e}"
                    ) from e
        elif hasattr(s3_client, "list_objects_v2"):
            resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            for obj in resp.get("Contents", []):
                key = obj.get("Key", "")
                if key.lower().endswith(".pdf"):
                    pdf_objects.append(obj)
        return pdf_objects
    except Pdf2CsvError:
        raise
    except (ClientError, BotoCoreError) as e:
        raise Pdf2CsvError(
            f"Ticket {ticket}: S3 read failure listing objects under 's3://{bucket}/{prefix}': {e}"
        ) from e
    except Exception as e:
        raise Pdf2CsvError(
            f"Ticket {ticket}: S3 read failure listing objects under 's3://{bucket}/{prefix}': {e}"
        ) from e


def handler(
    event: dict,
    context=None,
    s3_client=None,
    storage_budget: int = DEFAULT_EPHEMERAL_STORAGE_BUDGET,
) -> dict:
    """AWS Lambda entry point for PDF-to-CSV Normalizer stage.

    Args:
        event: Dict containing 'input-s3-uri'.
        context: Lambda context (unused).
        s3_client: Optional injected S3 client for testing.
        storage_budget: Optional max allowed input size in bytes.

    Returns:
        Dict with 'ticket', 'status', 'output-s3-uri'.

    Raises:
        Pdf2CsvError: On validation, S3 I/O, or conversion failure.
    """
    input_s3_uri, bucket, prefix, ticket = parse_and_validate_event(event)

    client = get_s3_client(s3_client)

    logger.info("Normalizer starting for ticket %s with URI %s", ticket, input_s3_uri)

    # 2. List all objects under the input prefix
    pdf_objects = list_pdf_objects(client, bucket, prefix, ticket)

    # 3. If no PDFs are found, raise Pdf2CsvError
    if not pdf_objects:
        raise Pdf2CsvError(f"Ticket {ticket}: no PDFs found at input path '{input_s3_uri}'")

    # 4. Check total size against ephemeral-storage budget
    total_size = sum(obj.get("Size", 0) for obj in pdf_objects)
    if total_size > storage_budget:
        raise Pdf2CsvError(
            f"Ticket {ticket}: total input size ({total_size} bytes) exceeds "
            f"ephemeral storage budget ({storage_budget} bytes)"
        )

    logger.info(
        "Ticket %s: found %d PDF(s) to process (%d bytes total)",
        ticket,
        len(pdf_objects),
        total_size,
    )

    # 5. Create temporary working directories
    temp_dir = tempfile.mkdtemp(prefix="normalizer_")
    input_dir = os.path.join(temp_dir, "input")
    output_dir = os.path.join(temp_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        basenames = [os.path.basename(obj.get("Key", "")) for obj in pdf_objects]
        has_unique_basenames = len(basenames) == len(set(basenames))

        pdf_mappings = []
        for i, obj in enumerate(pdf_objects):
            s3_key = obj["Key"]
            base_name = os.path.basename(s3_key)
            local_pdf_name = base_name if has_unique_basenames else f"{i}_{base_name}"
            local_pdf_path = os.path.join(input_dir, local_pdf_name)

            if local_pdf_name.lower().endswith(".pdf"):
                local_csv_name = local_pdf_name[:-4] + ".csv"
            else:
                local_csv_name = f"{local_pdf_name}.csv"
            local_csv_path = os.path.join(output_dir, local_csv_name)

            if s3_key.lower().endswith(".pdf"):
                s3_csv_key = s3_key[:-4] + ".csv"
            else:
                s3_csv_key = f"{s3_key}.csv"

            # Download PDF
            try:
                if hasattr(client, "download_file"):
                    client.download_file(Bucket=bucket, Key=s3_key, Filename=local_pdf_path)
                elif hasattr(client, "get_object"):
                    resp = client.get_object(Bucket=bucket, Key=s3_key)
                    with open(local_pdf_path, "wb") as f:
                        f.write(resp["Body"].read())
                else:
                    raise Pdf2CsvError(f"Ticket {ticket}: client has no download capability")
            except Pdf2CsvError:
                raise
            except Exception as e:
                raise Pdf2CsvError(
                    f"Ticket {ticket}: S3 read failure downloading key '{s3_key}': {e}"
                ) from e

            pdf_mappings.append((s3_key, local_pdf_path, local_csv_path, s3_csv_key))

        # 6. Invoke conversion
        try:
            exit_code = process_input(input_path=input_dir, output_path=output_dir)
            if exit_code != 0:
                raise Pdf2CsvError(
                    f"Ticket {ticket}: conversion failed for input path '{input_s3_uri}'"
                )
        except Pdf2CsvError:
            raise
        except Exception as e:
            raise Pdf2CsvError(
                f"Ticket {ticket}: conversion failed for input path '{input_s3_uri}': {e}"
            ) from e

        # 7. Upload produced CSVs and verify all inputs converted
        for s3_key, _local_pdf_path, local_csv_path, s3_csv_key in pdf_mappings:
            if not os.path.exists(local_csv_path):
                raise Pdf2CsvError(f"Ticket {ticket}: conversion produced no CSV for '{s3_key}'")

            try:
                with open(local_csv_path, "rb") as f:
                    csv_data = f.read()

                if hasattr(client, "put_object"):
                    client.put_object(
                        Bucket=bucket,
                        Key=s3_csv_key,
                        Body=csv_data,
                        ContentType="text/csv",
                    )
                elif hasattr(client, "upload_file"):
                    client.upload_file(
                        Filename=local_csv_path,
                        Bucket=bucket,
                        Key=s3_csv_key,
                        ExtraArgs={"ContentType": "text/csv"},
                    )
                else:
                    raise Pdf2CsvError(f"Ticket {ticket}: client has no upload capability")
            except Pdf2CsvError:
                raise
            except Exception as e:
                raise Pdf2CsvError(
                    f"Ticket {ticket}: S3 write failure uploading '{s3_csv_key}': {e}"
                ) from e

        logger.info(
            "Ticket %s: successfully converted and uploaded %d CSV(s)",
            ticket,
            len(pdf_mappings),
        )

        # 9. Return success response
        return {
            "ticket": ticket,
            "status": "SUCCEEDED",
            "output-s3-uri": input_s3_uri,
        }

    finally:
        # 8. Clean up temporary directories always
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
