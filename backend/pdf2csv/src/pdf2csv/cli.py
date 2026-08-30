"""CLI entrypoint for pdf2csv."""

import argparse
import sys

from pdf2csv.converter import process_input


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdf2csv",
        description="Convert PDF spending statements into CSV format.",
    )
    parser.add_argument(
        "inputPdf",
        help="Path or S3 URI to an input PDF file or a directory containing PDF files.",
    )
    parser.add_argument(
        "outputCsv",
        help="Path or S3 URI for output CSV directory or file.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI function.

    Args:
        argv: Optional list of command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    exit_code = process_input(
        input_path=args.inputPdf,
        output_path=args.outputCsv,
        debug=args.debug,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
