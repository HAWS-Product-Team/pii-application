"""
CLI entry point for Submit service.

Allows testing or invoking the submit batch upload flow from the terminal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from submit.lambda_handler import handler


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for batch upload initialization."""
    parser = argparse.ArgumentParser(
        description="Initialize a batch upload session, mint credentials, and generate presigned S3 URLs."
    )
    parser.add_argument(
        "--table-name",
        default=os.environ.get("TICKETS_TABLE_NAME"),
        help="DynamoDB tickets table name (default: TICKETS_TABLE_NAME env var)",
    )
    parser.add_argument(
        "--bucket-name",
        default=os.environ.get("UPLOADS_BUCKET_NAME"),
        help="S3 uploads bucket name (default: UPLOADS_BUCKET_NAME env var)",
    )
    parser.add_argument(
        "--files",
        help="JSON string or file path containing the 'files' array",
    )

    args = parser.parse_args(argv)

    if not args.table_name:
        sys.stderr.write(
            "Error: --table-name or TICKETS_TABLE_NAME environment variable is required\n"
        )
        return 1

    if not args.bucket_name:
        sys.stderr.write(
            "Error: --bucket-name or UPLOADS_BUCKET_NAME environment variable is required\n"
        )
        return 1

    files_input = args.files
    if not files_input:
        if not sys.stdin.isatty():
            files_input = sys.stdin.read().strip()
        else:
            sys.stderr.write("Error: --files argument or stdin with JSON payload is required\n")
            return 1

    try:
        if os.path.isfile(files_input):
            with open(files_input, encoding="utf-8") as f:
                parsed_json = json.load(f)
        else:
            parsed_json = json.loads(files_input)
    except (json.JSONDecodeError, OSError) as e:
        sys.stderr.write(f"Error parsing JSON input: {e}\n")
        return 1

    if isinstance(parsed_json, list):
        payload = {"files": parsed_json}
    elif isinstance(parsed_json, dict):
        payload = parsed_json
    else:
        sys.stderr.write("Error: payload must be a JSON object or array\n")
        return 1

    # Temporarily set env vars if provided via args
    os.environ["TICKETS_TABLE_NAME"] = args.table_name
    os.environ["UPLOADS_BUCKET_NAME"] = args.bucket_name

    response = handler({"body": json.dumps(payload)})
    status_code = response.get("statusCode", 500)
    body = response.get("body", "{}")

    if status_code == 200:
        sys.stdout.write(body + "\n")
        return 0
    else:
        sys.stderr.write(f"Error ({status_code}): {body}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
