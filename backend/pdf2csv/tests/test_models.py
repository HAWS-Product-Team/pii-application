"""Tests for data models."""

from dataclasses import FrozenInstanceError

import pytest

from pdf2csv.models import Record


def test_record_creation():
    r = Record(
        date="2026-08-26",
        item_description="Test Item",
        quantity=1,
        unit_price="34.62",
        total_price="34.62",
    )
    assert r.date == "2026-08-26"
    assert r.item_description == "Test Item"
    assert r.quantity == 1
    assert r.unit_price == "34.62"
    assert r.total_price == "34.62"


def test_record_immutability():
    r = Record(
        date="2026-08-26",
        item_description="Test Item",
        quantity=1,
        unit_price="34.62",
        total_price="34.62",
    )
    with pytest.raises(FrozenInstanceError):
        r.unit_price = "10.00"  # type: ignore
