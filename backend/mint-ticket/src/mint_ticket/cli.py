import argparse
import json
import os
import sys
from collections.abc import Sequence

from mint_ticket.issuer import mint_ticket


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket-issuer",
        description="Mint a new ticket and secret, storing the hash in DynamoDB.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--table-name",
        dest="table_name",
        default=None,
        help="DynamoDB table name (defaults to TICKETS_TABLE_NAME or DYNAMODB_TABLE_NAME env var)",
    )
    parser.add_argument(
        "--ttl-seconds",
        dest="ttl_seconds",
        type=int,
        default=86_400,
        help="Ticket time-to-live in seconds (default: 86400)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    table_name = (
        args.table_name
        or os.environ.get("TICKETS_TABLE_NAME")
        or os.environ.get("DYNAMODB_TABLE_NAME")
    )
    if not table_name:
        sys.stderr.write(
            "Error: DynamoDB table name must be specified via --table-name flag or "
            "TICKETS_TABLE_NAME / DYNAMODB_TABLE_NAME environment variable.\n"
        )
        sys.exit(1)

    try:
        result = mint_ticket(table_name=table_name, ttl_seconds=args.ttl_seconds)
        sys.stdout.write(json.dumps(result) + "\n")
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
