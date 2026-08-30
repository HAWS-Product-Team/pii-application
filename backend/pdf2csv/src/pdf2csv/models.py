"""Data models for pdf2csv."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Record:
    """Represents a single parsed transaction/order record."""

    date: str
    item_description: str
    quantity: int = 1
    unit_price: str = "0.00"
    total_price: str = "0.00"
