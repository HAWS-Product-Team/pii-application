"""Conversion orchestrator for pdf2csv."""

import os
import sys
from typing import TextIO

from pdf2csv.extractor import extract_text_lines
from pdf2csv.io import (
    derive_output_csv_path,
    discover_pdf_paths,
    is_s3_uri,
    read_pdf_bytes,
    write_csv_records,
)
from pdf2csv.models import Record
from pdf2csv.parsers import detect_parser

MAX_PDF_SIZE_BYTES = 32 * 1024 * 1024  # 32 MB


def convert_pdf_bytes(pdf_bytes: bytes) -> list[Record]:
    """Convert raw PDF bytes to Record objects.

    Args:
        pdf_bytes: Binary content of the PDF.

    Returns:
        List of parsed Record instances.

    Raises:
        ValueError: If file exceeds 32MB or zero records are extracted.
        ParserNotFoundError: If no matching parser is found for the first 10 lines.
    """
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        raise ValueError(f"File exceeds 32 MB size limit ({len(pdf_bytes)} bytes)")

    lines = extract_text_lines(pdf_bytes)
    parser = detect_parser(lines)
    records = parser.parse(lines)
    if not records:
        raise ValueError("Zero records extracted from PDF")
    return records


def process_input(
    input_path: str,
    output_path: str | None = None,
    stream: TextIO | None = None,
    err_stream: TextIO | None = None,
    s3_client=None,
    debug: bool = False,
) -> int:
    """Execute the end-to-end PDF-to-CSV processing pipeline.

    Args:
        input_path: Path or S3 URI to a PDF file or directory/prefix.
        output_path: Optional path or S3 URI to write the output CSV(s).
        stream: Stream for stdout.
        err_stream: Stream for stderr error messages.
        s3_client: Optional boto3 S3 client.
        debug: Whether to print debug information to stdout.

    Returns:
        0 on success, 1 on argument/discovery/whole-run error.
    """
    err = err_stream if err_stream is not None else sys.stderr
    out = stream if stream is not None else sys.stdout

    try:
        pdf_paths = discover_pdf_paths(input_path, s3_client=s3_client)
    except Exception as e:  # noqa: BLE001
        err.write(f"Error discovering PDFs: {e}\n")
        err.flush()
        return 1

    if not pdf_paths:
        err.write(f"No PDF files found at: {input_path}\n")
        err.flush()
        return 1

    # Validate output path if multiple PDFs are being processed
    if output_path is not None and len(pdf_paths) > 1 and not is_s3_uri(output_path):
        if os.path.isfile(output_path):
            err.write(f"Error: output_dir is an existing file, expected directory: {output_path}\n")
            err.flush()
            return 1
        os.makedirs(output_path, exist_ok=True)

    for path in pdf_paths:
        try:
            pdf_bytes = read_pdf_bytes(path, s3_client=s3_client)
            records = convert_pdf_bytes(pdf_bytes)

            if output_path is None:
                write_csv_records(
                    records,
                    output_path_or_uri=None,
                    stream=out,
                    s3_client=s3_client,
                )
            else:
                dest_csv = derive_output_csv_path(path, output_path)
                write_csv_records(
                    records,
                    output_path_or_uri=dest_csv,
                    s3_client=s3_client,
                )

            if debug:
                # Count distinct order headers from the parsed records
                unique_dates_items = len(records)
                out.write(f"Parsed orders from {path}: {unique_dates_items} items\n")
                out.flush()

        except Exception as e:  # noqa: BLE001
            err.write(f"Error processing {path}: {e}\n")
            err.flush()

    return 0
