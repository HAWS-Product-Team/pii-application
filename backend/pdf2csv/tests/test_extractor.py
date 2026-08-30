"""Tests for PDF text extraction."""

import io
import os

from pypdf import PdfWriter

from pdf2csv.extractor import extract_text_lines


def test_extract_text_from_file():
    pdf_dir = "data/AmazonOrderHistoryPDFs"
    if not os.path.isdir(pdf_dir):
        return
    files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    if not files:
        return
    path = os.path.join(pdf_dir, files[0])
    lines = extract_text_lines(path)
    assert len(lines) > 0
    assert any("Amazon" in l for l in lines)


def test_extract_text_from_bytes_and_stream():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    # From bytes
    lines_bytes = extract_text_lines(pdf_bytes)
    assert isinstance(lines_bytes, list)

    # From stream
    buf.seek(0)
    lines_stream = extract_text_lines(buf)
    assert isinstance(lines_stream, list)
