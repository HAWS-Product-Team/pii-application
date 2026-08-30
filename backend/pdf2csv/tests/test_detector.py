"""Tests for parser detection and registry."""

import pytest

from pdf2csv.models import Record
from pdf2csv.parsers import AmazonOrderHistoryParser
from pdf2csv.parsers.base import BaseParser
from pdf2csv.parsers.detector import (
    ParserNotFoundError,
    detect_parser,
    register_parser,
)


def test_detect_amazon_parser():
    lines = [
        "123Search Amazon",
        "Hello, Alice",
        "Your Orders",
        "ORDER PLACED",
        "August 26, 2026",
    ]
    parser = detect_parser(lines)
    assert isinstance(parser, AmazonOrderHistoryParser)


def test_parser_not_found_error_message():
    with pytest.raises(ParserNotFoundError) as exc_info:
        # Detect with lines that don't match any registered parser
        detect_parser(["Unknown Bank Statement", "Account #123", "Checking"])

    expected_msg = (
        "parser not found for first 10 lines:\nUnknown Bank Statement\nAccount #123\nChecking"
    )
    assert exc_info.value.message == expected_msg
    assert str(exc_info.value) == expected_msg


def test_custom_parser_registration():
    class DummyParser(BaseParser):
        def parse(self, lines: list[str]) -> list[Record]:
            return [Record("2026-01-01", "Dummy", 1, "10.00", "10.00")]

    register_parser(
        lambda first_10: any("DummyBank" in l for l in first_10),
        DummyParser,
    )

    detected = detect_parser(["Header", "Welcome to DummyBank Statement", "Balance"])
    assert isinstance(detected, DummyParser)
    records = detected.parse([])
    assert len(records) == 1
    assert records[0].item_description == "Dummy"
