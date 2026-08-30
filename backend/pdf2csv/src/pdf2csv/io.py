"""Input/Output and Storage module for local and S3 paths."""

import csv
import io
import os
import sys
from typing import TextIO
from urllib.parse import urlparse

import boto3

from pdf2csv.models import Record


def is_s3_uri(path: str) -> bool:
    """Check if a path string is an S3 URI."""
    return path.startswith("s3://")


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Split an S3 URI into (bucket, key)."""
    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def discover_pdf_paths(input_path: str, s3_client=None) -> list[str]:
    """Discover all PDF paths/URIs given a file or directory path (local or S3).

    Args:
        input_path: Local path or s3:// URI pointing to a PDF or a directory/prefix.
        s3_client: Optional boto3 S3 client.

    Returns:
        List of resolved PDF paths / S3 URIs in sorted order.

    Raises:
        FileNotFoundError: If the local path does not exist.
        ValueError: If no PDFs are found or S3 bucket/key is invalid.
    """
    if is_s3_uri(input_path):
        client = s3_client or boto3.client("s3")
        bucket, key = parse_s3_uri(input_path)
        if key.lower().endswith(".pdf"):
            return [input_path]

        # List objects under prefix
        prefix = key
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"

        paginator = client.get_paginator("list_objects_v2")
        pdf_uris = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                obj_key = obj["Key"]
                if obj_key.lower().endswith(".pdf"):
                    pdf_uris.append(f"s3://{bucket}/{obj_key}")
        return sorted(pdf_uris)

    # Local path
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    if os.path.isfile(input_path):
        if not input_path.lower().endswith(".pdf"):
            raise ValueError(f"Input file is not a PDF: {input_path}")
        return [os.path.abspath(input_path)]

    if os.path.isdir(input_path):
        pdf_paths = [
            os.path.abspath(os.path.join(input_path, f))
            for f in sorted(os.listdir(input_path))
            if f.lower().endswith(".pdf")
        ]
        return pdf_paths

    raise ValueError(f"Unsupported input path: {input_path}")


def read_pdf_bytes(pdf_path_or_uri: str, s3_client=None) -> bytes:
    """Read binary content of a PDF from local filesystem or S3.

    Args:
        pdf_path_or_uri: Local path or s3:// URI.
        s3_client: Optional boto3 S3 client.

    Returns:
        Bytes of the PDF file.
    """
    if is_s3_uri(pdf_path_or_uri):
        client = s3_client or boto3.client("s3")
        bucket, key = parse_s3_uri(pdf_path_or_uri)
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    with open(pdf_path_or_uri, "rb") as f:
        return f.read()


def derive_output_csv_path(input_pdf_path_or_uri: str, output_path_or_uri: str) -> str:
    """Derive the destination CSV path or S3 URI from the input PDF and output path.

    Args:
        input_pdf_path_or_uri: Path or S3 URI of the input PDF.
        output_path_or_uri: Directory path, file path, or S3 prefix/URI for output.

    Returns:
        Target CSV path or S3 URI.
    """
    raw_name = (
        os.path.basename(parse_s3_uri(input_pdf_path_or_uri)[1])
        if is_s3_uri(input_pdf_path_or_uri)
        else os.path.basename(input_pdf_path_or_uri)
    )
    # Replace .pdf (case-insensitive) with .csv, preserving base name exactly
    if raw_name.lower().endswith(".pdf"):
        csv_filename = raw_name[:-4] + ".csv"
    else:
        csv_filename = f"{raw_name}.csv"

    if is_s3_uri(output_path_or_uri):
        if output_path_or_uri.lower().endswith(".csv"):
            return output_path_or_uri
        prefix = output_path_or_uri.rstrip("/")
        return f"{prefix}/{csv_filename}"

    # Local path
    if output_path_or_uri.lower().endswith(".csv") and not os.path.isdir(output_path_or_uri):
        return output_path_or_uri

    return os.path.join(output_path_or_uri, csv_filename)


def write_csv_records(
    records: list[Record],
    output_path_or_uri: str | None = None,
    stream: TextIO | None = None,
    s3_client=None,
) -> None:
    """Write records to CSV format to stdout, a stream, a local file, or S3.

    Args:
        records: List of Record instances.
        output_path_or_uri: Optional destination path/URI. If None and stream is None, writes to sys.stdout.
        stream: Optional TextIO stream.
        s3_client: Optional boto3 S3 client.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["date", "item_description", "quantity", "unit_price", "total_price"])
    for r in records:
        writer.writerow([r.date, r.item_description, r.quantity, r.unit_price, r.total_price])

    csv_content = buffer.getvalue()

    if output_path_or_uri is None:
        target_stream = stream if stream is not None else sys.stdout
        target_stream.write(csv_content)
        target_stream.flush()
        return

    if is_s3_uri(output_path_or_uri):
        client = s3_client or boto3.client("s3")
        bucket, key = parse_s3_uri(output_path_or_uri)
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=csv_content.encode("utf-8"),
            ContentType="text/csv",
        )
        return

    # Local file
    parent = os.path.dirname(os.path.abspath(output_path_or_uri))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(output_path_or_uri, "w", encoding="utf-8", newline="") as f:
        f.write(csv_content)
