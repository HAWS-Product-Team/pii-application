"""Tests for AmazonOrderHistoryParser."""

import os

from pdf2csv.extractor import extract_text_lines
from pdf2csv.models import Record
from pdf2csv.parsers.amazon import (
    AmazonOrderHistoryParser,
    clean_description_text,
    parse_amount_str,
    parse_date_str,
)


def test_parse_date_and_amount_helpers():
    assert parse_date_str("August 26, 2026") == "2026-08-26"
    assert parse_date_str("Jan 5, 2026") == "2026-01-05"
    assert parse_date_str("2026-08-23") == "2026-08-23"

    assert parse_amount_str("$34.62") == "34.62"
    assert parse_amount_str("$1,234.50") == "1234.50"
    assert parse_amount_str("50.0") == "50.00"


def test_clean_description_text():
    raw = "Organic Almond Butter Return window closed on Sep 10, 2026"
    assert clean_description_text(raw) == "Organic Almond Butter"

    raw_prefix = (
        "Refund issued A refund will appear on your original payment method in 2-4 business days. "
        "Why is a refund being issued? USB-C Cable 6ft"
    )
    assert clean_description_text(raw_prefix) == "USB-C Cable 6ft"

    raw_recall = (
        "An item you have purchased has been recalled or has a safety alert Safety Plug Protectors"
    )
    assert clean_description_text(raw_recall) == "Safety Plug Protectors"


def test_single_item_multi_line_anchor():
    lines = [
        "Search Amazon",
        "Your Orders",
        "ORDER PLACED",
        "August 26, 2026",
        "TOTAL",
        "$34.62",
        "SHIP TO Alice",
        "ORDER # 112-8874130-1097834",
        "Delivered August 28",
        "Your package was left near the front door",
        "Bose QuietComfort Wireless Noise Cancelling",
        "Over-Ear Headphones - Triple Black",
        "Return window closed on Sep 28, 2026",
        "Buy it again",
        "Write a product review",
    ]
    parser = AmazonOrderHistoryParser()
    records = parser.parse(lines)
    assert len(records) == 1
    assert records[0] == Record(
        date="2026-08-26",
        item_description="Bose QuietComfort Wireless Noise Cancelling Over-Ear Headphones - Triple Black",
        quantity=1,
        unit_price="34.62",
        total_price="34.62",
    )


def test_single_line_anchor_format():
    lines = [
        "Search Amazon",
        "ORDER PLACED TOTAL SHIP TO ORDER # 114-1234567-7654321",
        "July 15, 2026 $19.99 Bob",
        "Delivered July 18",
        "Stainless Steel Water Bottle 32oz",
        "Buy it again",
    ]
    parser = AmazonOrderHistoryParser()
    records = parser.parse(lines)
    assert len(records) == 1
    assert records[0] == Record(
        date="2026-07-15",
        item_description="Stainless Steel Water Bottle 32oz",
        quantity=1,
        unit_price="19.99",
        total_price="19.99",
    )


def test_multi_item_order_with_quantity():
    lines = [
        "Search Amazon",
        "ORDER PLACED",
        "June 30, 2026",
        "TOTAL",
        "$55.00",
        "ORDER # 111-2223334-5556667",
        "Delivered July 2",
        "2",
        "Amazon Grocery Tonic Water 33.8 Oz",
        "Buy it again",
        "Basesailor USB to USB C Adapter 3Pack",
        "Buy it again",
    ]
    parser = AmazonOrderHistoryParser()
    records = parser.parse(lines)
    assert len(records) == 2
    assert records[0].date == "2026-06-30"
    assert records[0].item_description == "Amazon Grocery Tonic Water 33.8 Oz"
    assert records[0].quantity == 1
    assert records[0].unit_price == "27.50"
    assert records[0].total_price == "27.50"

    assert records[1].date == "2026-06-30"
    assert records[1].item_description == "Basesailor USB to USB C Adapter 3Pack"
    assert records[1].quantity == 1
    assert records[1].unit_price == "27.50"
    assert records[1].total_price == "27.50"


def test_refund_order_dropped():
    lines = [
        "Search Amazon",
        "ORDER PLACED",
        "May 1, 2026",
        "TOTAL",
        "$19.47",
        "ORDER # 113-6506281-3975409",
        "Delivered May 3",
        "Refund issued A refund will appear on your original payment method in 2-4 business days.",
        "SHINESTAR Grill Plates",
        "Buy it again",
    ]
    parser = AmazonOrderHistoryParser()
    records = parser.parse(lines)
    assert len(records) == 0


def test_even_split_rounding_cents():
    lines = [
        "Search Amazon",
        "ORDER PLACED",
        "July 11, 2026",
        "TOTAL",
        "$89.83",
        "ORDER # 112-9944099-3660251",
        "Delivered July 13",
        "Amazon Basics AA Batteries",
        "Buy it again",
        "Tesla Adapter",
        "Buy it again",
    ]
    parser = AmazonOrderHistoryParser()
    records = parser.parse(lines)
    assert len(records) == 2
    assert records[0].unit_price == "44.92"
    assert records[0].total_price == "44.92"
    assert records[1].unit_price == "44.91"
    assert records[1].total_price == "44.91"


def test_footer_patterns_terminate_item_parsing():
    lines = [
        "Search Amazon",
        "ORDER PLACED",
        "May 10, 2026",
        "TOTAL",
        "$12.00",
        "ORDER # 111-0000000-0000000",
        "Delivered May 12",
        "Desk Lamp LED",
        "Buy it again",
        "←Previous 1 2 3 Next→",
        "Customers who viewed items you recently viewed",
        "Conditions of Use Privacy Notice",
    ]
    parser = AmazonOrderHistoryParser()
    records = parser.parse(lines)
    assert len(records) == 1
    assert records[0].item_description == "Desk Lamp LED"


def test_all_sample_pdfs():
    pdf_dir = "data/AmazonOrderHistoryPDFs"
    if not os.path.isdir(pdf_dir):
        return

    parser = AmazonOrderHistoryParser()
    total_records = 0
    for fname in sorted(os.listdir(pdf_dir)):
        if not fname.endswith(".pdf"):
            continue
        lines = extract_text_lines(os.path.join(pdf_dir, fname))
        recs = parser.parse(lines)
        assert len(recs) > 0, f"Failed to parse any orders from {fname}"
        for r in recs:
            assert len(r.date.split("-")) == 3
            assert r.quantity == 1
            assert float(r.unit_price) >= 0.0
            assert float(r.total_price) >= 0.0
        total_records += len(recs)

    assert total_records > 0
