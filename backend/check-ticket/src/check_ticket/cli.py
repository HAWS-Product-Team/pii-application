"""
CLI entry point for Check Ticket authorizer service.

Allows testing or invoking authorization flows directly from the terminal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from check_ticket.lambda_handler import handler

DEFAULT_METHOD_ARN = (
    "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status"
)


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Validate ticket credentials against DynamoDB and output API Gateway IAM policy.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--table-name",
        default=None,
        help="DynamoDB tickets table name (default: TICKETS_TABLE_NAME or DYNAMODB_TABLE_NAME env var)",
    )
    parser.add_argument(
        "--auth-header",
        "--authorization",
        dest="auth_header",
        default=None,
        help="HTTP Authorization header value (e.g. 'Ticket <ticket_id>:<secret>')",
    )
    parser.add_argument(
        "--ticket-id",
        dest="ticket_id",
        default=None,
        help="Ticket ULID (convenience option alternative to --auth-header)",
    )
    parser.add_argument(
        "--secret",
        dest="secret",
        default=None,
        help="Raw bearer secret (convenience option alternative to --auth-header)",
    )
    parser.add_argument(
        "--method-arn",
        dest="method_arn",
        default=DEFAULT_METHOD_ARN,
        help=f"Simulated API Gateway method ARN (default: {DEFAULT_METHOD_ARN})",
    )
    parser.add_argument(
        "--event",
        dest="event",
        default=None,
        help="JSON string or file path containing an API Gateway authorizer event payload",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for ticket authorizer validation."""
    parser = build_parser()
    args = parser.parse_args(argv)

    table_name = (
        args.table_name
        or os.environ.get("TICKETS_TABLE_NAME")
        or os.environ.get("DYNAMODB_TABLE_NAME")
    )
    if not table_name:
        sys.stderr.write(
            "Error: --table-name or TICKETS_TABLE_NAME environment variable is required\n"
        )
        return 1

    method_arn = args.method_arn or DEFAULT_METHOD_ARN
    event_payload: dict | None = None

    if args.event:
        try:
            if os.path.isfile(args.event):
                with open(args.event, encoding="utf-8") as f:
                    event_payload = json.load(f)
            else:
                event_payload = json.loads(args.event)
        except (json.JSONDecodeError, OSError) as exc:
            sys.stderr.write(f"Error parsing event JSON: {exc}\n")
            return 1

        if not isinstance(event_payload, dict):
            sys.stderr.write("Error: Event payload must be a JSON object\n")
            return 1

        if "methodArn" not in event_payload and "method_arn" not in event_payload:
            event_payload["methodArn"] = method_arn

    elif args.auth_header:
        event_payload = {
            "authorizationToken": args.auth_header,
            "methodArn": method_arn,
        }

    elif args.ticket_id or args.secret:
        if not args.ticket_id or not args.secret:
            sys.stderr.write("Error: Both --ticket-id and --secret must be provided together\n")
            return 1
        event_payload = {
            "authorizationToken": f"Ticket {args.ticket_id}:{args.secret}",
            "methodArn": method_arn,
        }

    else:
        if not sys.stdin.isatty():
            stdin_data = sys.stdin.read().strip()
            if not stdin_data:
                sys.stderr.write("Error: Empty input from stdin\n")
                return 1

            # Try parsing stdin as JSON event payload
            try:
                parsed_stdin = json.loads(stdin_data)
                if isinstance(parsed_stdin, dict):
                    event_payload = parsed_stdin
                    if "methodArn" not in event_payload and "method_arn" not in event_payload:
                        event_payload["methodArn"] = method_arn
            except json.JSONDecodeError:
                pass

            if event_payload is None:
                # Treat raw stdin data as authorization header string
                event_payload = {
                    "authorizationToken": stdin_data,
                    "methodArn": method_arn,
                }
        else:
            sys.stderr.write(
                "Error: Input credentials required via --auth-header, --ticket-id/--secret, --event, or stdin\n"
            )
            return 1

    os.environ["TICKETS_TABLE_NAME"] = table_name

    try:
        policy = handler(event_payload)
        sys.stdout.write(json.dumps(policy, indent=2) + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"Error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
