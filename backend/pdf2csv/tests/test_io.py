"""Tests for IO and S3 integration."""

import io
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from pdf2csv.io import (
    derive_output_csv_path,
    discover_pdf_paths,
    is_s3_uri,
    parse_s3_uri,
    read_pdf_bytes,
    write_csv_records,
)
from pdf2csv.models import Record


def test_derive_output_csv_path():
    # Local directory output
    assert derive_output_csv_path("path/to/sample.pdf", "output_dir") == os.path.join(
        "output_dir", "sample.csv"
    )
    # Local file output
    assert (
        derive_output_csv_path("path/to/sample.pdf", "output_dir/custom.csv")
        == "output_dir/custom.csv"
    )

    # S3 URI output prefix
    assert (
        derive_output_csv_path("s3://bucket/in/sample.pdf", "s3://bucket/out")
        == "s3://bucket/out/sample.csv"
    )
    assert (
        derive_output_csv_path("s3://bucket/in/sample.pdf", "s3://bucket/out/")
        == "s3://bucket/out/sample.csv"
    )
    # S3 URI explicit file
    assert (
        derive_output_csv_path("s3://bucket/in/sample.pdf", "s3://bucket/out/custom.csv")
        == "s3://bucket/out/custom.csv"
    )


def test_is_s3_uri():
    assert is_s3_uri("s3://my-bucket/path/to/file.pdf")
    assert not is_s3_uri("/local/path/to/file.pdf")
    assert not is_s3_uri("data/file.pdf")


def test_parse_s3_uri():
    bucket, key = parse_s3_uri("s3://test-bucket/folder/statement.pdf")
    assert bucket == "test-bucket"
    assert key == "folder/statement.pdf"

    bucket, key = parse_s3_uri("s3://test-bucket")
    assert bucket == "test-bucket"
    assert key == ""


def test_discover_local_pdf_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        f1 = os.path.join(tmpdir, "a.pdf")
        f2 = os.path.join(tmpdir, "b.pdf")
        txt = os.path.join(tmpdir, "c.txt")
        for f in (f1, f2, txt):
            with open(f, "w") as fp:
                fp.write("dummy")

        discovered = discover_pdf_paths(tmpdir)
        assert len(discovered) == 2
        assert f1 in discovered
        assert f2 in discovered

        single = discover_pdf_paths(f1)
        assert single == [f1]

        with pytest.raises(ValueError):
            discover_pdf_paths(txt)


def test_discover_pdf_paths_not_found():
    with pytest.raises(FileNotFoundError):
        discover_pdf_paths("/path/that/does/not/exist/anywhere")


def test_discover_s3_pdf_paths():
    mock_s3 = MagicMock()
    mock_paginator = MagicMock()
    mock_s3.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {"Key": "statements/2026-01.pdf"},
                {"Key": "statements/2026-02.pdf"},
                {"Key": "statements/notes.txt"},
            ]
        }
    ]

    # Single S3 file
    single = discover_pdf_paths("s3://my-bucket/orders.pdf", s3_client=mock_s3)
    assert single == ["s3://my-bucket/orders.pdf"]

    # S3 Prefix
    multiple = discover_pdf_paths("s3://my-bucket/statements/", s3_client=mock_s3)
    assert len(multiple) == 2
    assert "s3://my-bucket/statements/2026-01.pdf" in multiple
    assert "s3://my-bucket/statements/2026-02.pdf" in multiple


def test_read_pdf_bytes_local_and_s3():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(b"SAMPLE_PDF_DATA")
        tf_path = tf.name

    try:
        data = read_pdf_bytes(tf_path)
        assert data == b"SAMPLE_PDF_DATA"
    finally:
        os.remove(tf_path)

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"S3_PDF_DATA")}
    s3_data = read_pdf_bytes("s3://my-bucket/file.pdf", s3_client=mock_s3)
    assert s3_data == b"S3_PDF_DATA"


def test_write_csv_records():
    records = [
        Record("2026-08-26", 'Bose QuietComfort "Special", Black', 1, "34.62", "34.62"),
        Record("2026-07-15", "Stainless Steel Water Bottle", 1, "19.99", "19.99"),
    ]

    # To stream
    stream = io.StringIO()
    write_csv_records(records, stream=stream)
    content = stream.getvalue()
    assert "date,item_description,quantity,unit_price,total_price" in content
    assert '2026-08-26,"Bose QuietComfort ""Special"", Black",1,34.62,34.62' in content

    # To local file
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        out_path = tf.name

    try:
        write_csv_records(records, output_path_or_uri=out_path)
        with open(out_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        assert file_content == content
    finally:
        os.remove(out_path)

    # To S3
    mock_s3 = MagicMock()
    write_csv_records(records, output_path_or_uri="s3://my-bucket/output.csv", s3_client=mock_s3)
    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "my-bucket"
    assert call_kwargs["Key"] == "output.csv"
    assert call_kwargs["ContentType"] == "text/csv"
    assert call_kwargs["Body"] == content.encode("utf-8")
