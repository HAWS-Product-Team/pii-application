"""Additional edge case tests to reach maximum branch coverage."""

import os
import tempfile
from unittest.mock import MagicMock

from pdf2csv.converter import process_input
from pdf2csv.io import discover_pdf_paths, write_csv_records
from pdf2csv.models import Record
from pdf2csv.parsers.amazon import parse_amount_str, parse_date_str
from pdf2csv.parsers.base import BaseParser
from pdf2csv.parsers.detector import clear_registry


def test_clear_registry():
    import importlib

    import pdf2csv.parsers

    clear_registry()
    # Re-import to re-register
    importlib.reload(pdf2csv.parsers)


def test_process_input_empty_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = []
        err = []
        exit_code = process_input(
            tmpdir,
            stream=MagicMock(write=lambda s: out.append(s)),
            err_stream=MagicMock(write=lambda s: err.append(s)),
        )
        assert exit_code == 1
        assert any("No PDF files found" in msg for msg in err)


def test_process_input_write_failure():
    pdf_dir = "data/AmazonOrderHistoryPDFs"
    files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    sample_pdf = os.path.join(pdf_dir, files[0])

    mock_stream = MagicMock()
    mock_stream.write.side_effect = OSError("Disk full")

    err = []
    exit_code = process_input(
        sample_pdf,
        stream=mock_stream,
        err_stream=MagicMock(write=lambda s: err.append(s)),
    )
    assert exit_code == 0
    assert any("Error processing" in msg for msg in err)


def test_io_create_parent_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_out = os.path.join(tmpdir, "subdir", "deep", "output.csv")
        records = [Record("2026-01-01", "Item", 1, "10.00", "10.00")]
        write_csv_records(records, output_path_or_uri=nested_out)
        assert os.path.exists(nested_out)


def test_convert_pdf_size_limit():
    import pytest

    from pdf2csv.converter import convert_pdf_bytes

    huge_bytes = b"0" * (33 * 1024 * 1024)
    with pytest.raises(ValueError) as excinfo:
        convert_pdf_bytes(huge_bytes)
    assert "exceeds 32 MB size limit" in str(excinfo.value)


def test_convert_pdf_zero_records(mocker):
    import pytest

    from pdf2csv.converter import convert_pdf_bytes

    mocker.patch("pdf2csv.converter.extract_text_lines", return_value=["Search Amazon"])
    with pytest.raises(ValueError) as excinfo:
        convert_pdf_bytes(b"dummy")
    assert "Zero records extracted" in str(excinfo.value)


def test_multiple_pdfs_with_file_output_error():
    pdf_dir = "data/AmazonOrderHistoryPDFs"
    with tempfile.NamedTemporaryFile(suffix=".csv") as tf:
        err = []
        exit_code = process_input(
            pdf_dir,
            output_path=tf.name,
            err_stream=MagicMock(write=lambda s: err.append(s)),
        )
        assert exit_code == 1
        assert any("output_dir is an existing file" in msg for msg in err)


def test_s3_prefix_without_trailing_slash():
    mock_s3 = MagicMock()
    mock_paginator = MagicMock()
    mock_s3.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [{"Contents": [{"Key": "statements/2026-01.pdf"}]}]

    discovered = discover_pdf_paths("s3://my-bucket/statements", s3_client=mock_s3)
    assert discovered == ["s3://my-bucket/statements/2026-01.pdf"]


def test_amazon_parser_fallback_parsing():
    # Test invalid date / amount fallback
    assert parse_date_str("Not a date") == "Not a date"
    assert parse_amount_str("InvalidAmount") == "InvalidAmount"

    # Test base parser directly
    class SimpleParser(BaseParser):
        def parse(self, lines: list[str]) -> list[Record]:
            return super().parse(lines)  # type: ignore

    p = SimpleParser()
    assert p.parse([]) is None
