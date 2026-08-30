"""Base parser interface for PDF statements."""

from abc import ABC, abstractmethod

from pdf2csv.models import Record


class BaseParser(ABC):
    """Abstract base class for statement parsers."""

    @abstractmethod
    def parse(self, lines: list[str]) -> list[Record]:
        """Parse extracted lines into a list of Record objects.

        Args:
            lines: List of text lines extracted from the PDF.

        Returns:
            List of parsed Record instances.
        """
