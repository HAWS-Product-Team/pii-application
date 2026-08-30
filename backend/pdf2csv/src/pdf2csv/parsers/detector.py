"""Parser detector and registry."""

from collections.abc import Callable

from pdf2csv.parsers.base import BaseParser


class ParserNotFoundError(Exception):
    """Raised when no registered parser matches the extracted text."""

    def __init__(self, first_10_lines: list[str]):
        lines_joined = "\n".join(first_10_lines[:10])
        self.message = f"parser not found for first 10 lines:\n{lines_joined}"
        super().__init__(self.message)


# Registry of (checker_fn, parser_factory_fn)
_REGISTRY: list[tuple[Callable[[list[str]], bool], Callable[[], BaseParser]]] = []


def register_parser(
    checker: Callable[[list[str]], bool],
    factory: Callable[[], BaseParser],
) -> None:
    """Register a parser detection rule and its factory.

    Args:
        checker: A callable taking the first 10 extracted lines and returning True if matched.
        factory: A callable creating an instance of BaseParser.
    """
    _REGISTRY.append((checker, factory))


def clear_registry() -> None:
    """Clear registered parsers (primarily for testing)."""
    _REGISTRY.clear()


def detect_parser(lines: list[str]) -> BaseParser:
    """Inspect the first 10 lines of extracted text and return matching parser.

    Args:
        lines: All extracted lines from the PDF.

    Returns:
        An instantiated BaseParser suitable for this PDF.

    Raises:
        ParserNotFoundError: When no registered parser matches.
    """
    first_10 = lines[:10]
    for checker, factory in _REGISTRY:
        if checker(first_10):
            return factory()
    raise ParserNotFoundError(first_10)
