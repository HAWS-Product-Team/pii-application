"""Parsers package initialization and registration."""

from pdf2csv.parsers.amazon import AmazonOrderHistoryParser
from pdf2csv.parsers.base import BaseParser
from pdf2csv.parsers.detector import ParserNotFoundError, detect_parser, register_parser


def _is_amazon_order_history(first_10_lines: list[str]) -> bool:
    """Check if any of the first 10 lines contains 'Amazon'."""
    return any("Amazon" in line for line in first_10_lines)


register_parser(_is_amazon_order_history, AmazonOrderHistoryParser)

__all__ = [
    "AmazonOrderHistoryParser",
    "BaseParser",
    "ParserNotFoundError",
    "detect_parser",
    "register_parser",
]
