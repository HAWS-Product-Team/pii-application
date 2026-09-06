"""Command-line entry point for the CSV merge step.

This layer only parses arguments and prints results. All logic lives in
``merger.merge_csv_files``, which never touches sys.argv, so it can be unit
tested without any CLI scaffolding.

    python -m merge.cli ./out/csv ./out/merged.csv
    python -m merge.cli ./out/csv ./out/merged.csv --verbose
    python -m merge.cli s3://bucket/tickets/123/csv \
                            s3://bucket/tickets/123/merged.csv
"""

from __future__ import annotations

import argparse
import sys

from .merger import DEFAULT_SOURCE_COLUMN, MergeError, merge_csv_files
from .storage import AutoStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-merge",
        description="Merge a directory of single-schema CSVs into one CSV.",
    )
    parser.add_argument(
        "input",
        help="Input directory or s3:// prefix containing the CSV files to merge (must be a directory)",
    )
    parser.add_argument(
        "output",
        help="Output CSV file path or s3:// URI to which the merged CSV will be written",
    )
    parser.add_argument(
        "--source-column",
        default=DEFAULT_SOURCE_COLUMN,
        help=f"Name of the appended origin-filename column when --verbose is used (default: {DEFAULT_SOURCE_COLUMN})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Write the file source column to the merged CSV and display the per-file summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    source_column = args.source_column if args.verbose else None

    try:
        result = merge_csv_files(
            storage=AutoStorage(),
            input_location=args.input,
            output_path=args.output,
            source_column=source_column,
        )
    except MergeError as exc:
        print(f"merge failed: {exc}", file=sys.stderr)
        return 1

    if args.verbose:
        for name, count in result.rows_per_file.items():
            print(f"  {name}: {count} rows")
    print(
        f"merged {result.file_count} files -> {result.output_path} "
        f"({result.total_rows} rows)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
