"""PDF text extraction module."""

import io
import logging
import warnings
from typing import BinaryIO

from pypdf import PdfReader

# Suppress noisy pypdf internal warnings
logging.getLogger("pypdf").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", module="pypdf")


def extract_text_lines(source: BinaryIO | bytes | str) -> list[str]:
    """Extract native text lines in page order from a PDF file, stream, or bytes.

    Args:
        source: PDF file path (str), bytes, or open binary stream.

    Returns:
        List of non-empty stripped text lines in extraction order.
    """
    if isinstance(source, bytes):
        reader = PdfReader(io.BytesIO(source))
    elif isinstance(source, str):
        reader = PdfReader(source)
    else:
        reader = PdfReader(source)

    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
    return lines
