"""AWS Lambda handler for the CSV merge step.

Unpacks the event, calls the core, shapes the response. No merge logic here.

Expected event:

    {
      "ticket_number": "abc-123",
      "input_location": "s3://bucket/tickets/abc-123/csv",
      "output_path": "s3://bucket/tickets/abc-123/merged.csv",
      "source_column": "source_file"          # optional
    }
"""

from __future__ import annotations

import logging
import os

from .merger import DEFAULT_SOURCE_COLUMN, MergeError, merge_csv_files
from .storage import AutoStorage

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event, context, storage=None):
    """Merge the ticket's CSVs and report what was written.

    ``storage`` is injectable so tests can drive the handler without S3.
    """
    ticket_number = event.get("ticket_number")

    try:
        input_location = event["input_location"]
        if "output_path" in event:
            output_path = event["output_path"]
        elif "output_location" in event:
            output_path = event["output_location"]
        else:
            raise KeyError("output_path")
    except KeyError as exc:
        raise ValueError(f"Missing required event field: {exc.args[0]}") from None

    source_column = event.get("source_column")
    if source_column is None and event.get("verbose"):
        source_column = DEFAULT_SOURCE_COLUMN

    logger.info(
        "merging CSVs ticket=%s input=%s output=%s",
        ticket_number,
        input_location,
        output_path,
    )

    try:
        result = merge_csv_files(
            storage=storage or AutoStorage(),
            input_location=input_location,
            output_path=output_path,
            source_column=source_column,
        )
    except MergeError as exc:
        logger.error("merge failed ticket=%s: %s", ticket_number, exc)
        raise

    logger.info(
        "merged ticket=%s files=%d rows=%d",
        ticket_number,
        result.file_count,
        result.total_rows,
    )

    return {
        "ticket_number": ticket_number,
        "output_path": result.output_path,
        "file_count": result.file_count,
        "total_rows": result.total_rows,
        "rows_per_file": result.rows_per_file,
    }
