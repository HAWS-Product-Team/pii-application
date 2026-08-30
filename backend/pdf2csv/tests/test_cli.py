"""Tests for converter and CLI entrypoint."""

import io
import os
import tempfile

from pdf2csv.cli import main
from pdf2csv.converter import process_input


def test_process_input_single_file():
    pdf_dir = "data/AmazonOrderHistoryPDFs"
    files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    sample_pdf = os.path.join(pdf_dir, files[0])

    out = io.StringIO()
    err = io.StringIO()
    exit_code = process_input(sample_pdf, stream=out, err_stream=err)

    assert exit_code == 0
    assert err.getvalue() == ""
    assert "date,item_description,quantity,unit_price,total_price" in out.getvalue()


def test_process_input_directory():
    pdf_dir = "data/AmazonOrderHistoryPDFs"
    with tempfile.TemporaryDirectory() as tmp_out:
        err = io.StringIO()
        exit_code = process_input(pdf_dir, output_path=tmp_out, err_stream=err)

        assert exit_code == 0
        assert err.getvalue() == ""
        csv_files = [f for f in os.listdir(tmp_out) if f.endswith(".csv")]
        assert len(csv_files) == 7
        for c in csv_files:
            with open(os.path.join(tmp_out, c), "r", encoding="utf-8") as f:
                content = f.read()
            assert "date,item_description,quantity,unit_price,total_price" in content


def test_process_input_nonexistent_path():
    out = io.StringIO()
    err = io.StringIO()
    exit_code = process_input("nonexistent/path/file.pdf", stream=out, err_stream=err)

    assert exit_code == 1
    assert "Error discovering PDFs" in err.getvalue()


def test_process_input_partial_failure():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create one valid PDF and one corrupted PDF
        valid_pdf = os.path.join(tmpdir, "valid.pdf")
        src_valid = os.path.join(
            "data/AmazonOrderHistoryPDFs", os.listdir("data/AmazonOrderHistoryPDFs")[0]
        )
        with open(src_valid, "rb") as sf, open(valid_pdf, "wb") as df:
            df.write(sf.read())

        corrupt_pdf = os.path.join(tmpdir, "corrupt.pdf")
        with open(corrupt_pdf, "wb") as f:
            f.write(b"NOT_A_VALID_PDF_STREAM")

        out = io.StringIO()
        err = io.StringIO()
        exit_code = process_input(tmpdir, stream=out, err_stream=err)

        assert exit_code == 0  # Section 8: per-PDF failure does not abort run or fail whole run
        assert "Error processing" in err.getvalue()
        # Valid records are still emitted
        assert "date,item_description,quantity,unit_price,total_price" in out.getvalue()


def test_cli_main_missing_arguments():
    import pytest

    # No arguments
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code != 0

    # Only one argument
    with pytest.raises(SystemExit) as excinfo:
        main(["dummy_input.pdf"])
    assert excinfo.value.code != 0


def test_cli_main_two_arguments():
    pdf_path = os.path.join(
        "data/AmazonOrderHistoryPDFs", os.listdir("data/AmazonOrderHistoryPDFs")[0]
    )
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        out_csv = tf.name

    try:
        exit_code = main([pdf_path, out_csv])
        assert exit_code == 0
        with open(out_csv, "r", encoding="utf-8") as f:
            content = f.read()
        assert "date,item_description,quantity,unit_price,total_price" in content
    finally:
        if os.path.exists(out_csv):
            os.remove(out_csv)


def test_cli_main_directory_to_directory():
    pdf_dir = "data/AmazonOrderHistoryPDFs"
    with tempfile.TemporaryDirectory() as tmp_out:
        exit_code = main([pdf_dir, tmp_out, "--debug"])
        assert exit_code == 0
        csv_files = [f for f in os.listdir(tmp_out) if f.endswith(".csv")]
        assert len(csv_files) == 7


def test_cli_run_as_module():
    import subprocess
    import sys

    pdf_path = os.path.join(
        "data/AmazonOrderHistoryPDFs", os.listdir("data/AmazonOrderHistoryPDFs")[0]
    )
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        out_csv = tf.name

    try:
        res = subprocess.run(
            [sys.executable, "-m", "pdf2csv.cli", pdf_path, out_csv],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0
        with open(out_csv, "r", encoding="utf-8") as f:
            content = f.read()
        assert "date,item_description,quantity,unit_price,total_price" in content
    finally:
        if os.path.exists(out_csv):
            os.remove(out_csv)
