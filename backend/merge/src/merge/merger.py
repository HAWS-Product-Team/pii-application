"""Merge a directory of single-schema CSVs into one CSV.

Runs between the PDF-to-CSV step and the normalizer. Streams row by row, so
memory stays flat no matter how many files or rows come through.

Two guards, both of which fail loudly rather than passing bad data downstream
to the classifier:

1. Header validation - every input file must have identical column headers.
2. Row count verification - the merged file is read back and its data rows
   counted against the sum of the per-file counts.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SOURCE_COLUMN = "source_file"


class MergeError(Exception):
    """Base class for every failure this step raises."""


class NoInputFilesError(MergeError):
    """The input location contained no CSV files."""


class HeaderMismatchError(MergeError):
    """Two input files disagreed on their column headers."""


class MalformedRowError(MergeError):
    """A row had a different number of fields than the header."""


class RowCountMismatchError(MergeError):
    """The merged file's row count didn't match the sum of the inputs."""


@dataclass
class MergeResult:
    """What the merge produced, for logging and for the Lambda response."""

    output_path: str
    header: list[str]
    total_rows: int
    rows_per_file: dict[str, int] = field(default_factory=dict)

    @property
    def file_count(self) -> int:
        return len(self.rows_per_file)


def merge_csv_files(
    storage,
    input_location: str,
    output_path: str | None = None,
    source_column: str | None = None,
    *,
    output_location: str | None = None,
) -> MergeResult:
    """Concatenate every CSV under ``input_location`` into ``output_path``.

    Args:
        storage: A ``Storage`` implementation (local, S3, or auto-routing).
        input_location: Directory or s3:// prefix holding the input CSVs.
        output_path: File path or s3:// URI where the merged CSV will be written.
        source_column: Optional name of the appended column holding the origin filename.
        output_location: Optional alias for output_path.

    Returns:
        A ``MergeResult`` describing what was written.

    Raises:
        MergeError: On any of the failure modes described in the module docstring.
    """
    resolved_output_path = output_path or output_location
    if resolved_output_path is None:
        raise ValueError("output_path is required")

    if (
        not resolved_output_path.startswith("s3://")
        and Path(resolved_output_path).is_dir()
    ):
        raise MergeError(
            f"Output path is a directory, expected a file: {resolved_output_path}"
        )

    try:
        paths = storage.list_csvs(input_location)
    except NotADirectoryError as exc:
        raise MergeError(
            f"Input location is not a directory: {input_location}"
        ) from exc

    if not paths:
        raise NoInputFilesError(f"No CSV files found under: {input_location}")

    header: list[str] = []
    rows_per_file: dict[str, int] = {}

    with storage.open_write(resolved_output_path) as out_handle:
        writer = csv.writer(out_handle)

        for path in paths:
            source_name = storage.basename(path)

            with storage.open_read(path) as in_handle:
                reader = csv.reader(in_handle)

                try:
                    file_header = next(reader)
                except StopIteration:
                    raise MergeError(f"Input file is empty: {path}") from None

                if not header:
                    header = file_header
                    if source_column and source_column in header:
                        raise MergeError(
                            f"Input files already contain a '{source_column}' "
                            f"column; pass a different source column name"
                        )
                    out_header = header + [source_column] if source_column else header
                    writer.writerow(out_header)
                elif file_header != header:
                    raise HeaderMismatchError(
                        f"Header mismatch in {source_name}.\n"
                        f"  expected: {header}\n"
                        f"  found:    {file_header}"
                    )

                count = 0
                for line_no, row in enumerate(reader, start=2):
                    if not row:
                        continue  # tolerate blank trailing lines
                    if len(row) != len(header):
                        raise MalformedRowError(
                            f"{source_name} line {line_no}: expected "
                            f"{len(header)} fields, found {len(row)}"
                        )
                    out_row = row + [source_name] if source_column else row
                    writer.writerow(out_row)
                    count += 1

                rows_per_file[source_name] = count

    expected_rows = sum(rows_per_file.values())
    actual_rows = _count_data_rows(storage, resolved_output_path)
    if actual_rows != expected_rows:
        raise RowCountMismatchError(
            f"Merged file has {actual_rows} data rows, expected {expected_rows} "
            f"from {len(rows_per_file)} input files"
        )

    return MergeResult(
        output_path=resolved_output_path,
        header=header + [source_column] if source_column else header,
        total_rows=actual_rows,
        rows_per_file=rows_per_file,
    )


def _count_data_rows(storage, path: str) -> int:
    """Read the merged file back and count its data rows (excluding header)."""
    with storage.open_read(path) as handle:
        reader = csv.reader(handle)
        next(reader, None)  # discard header
        return sum(1 for row in reader if row)
