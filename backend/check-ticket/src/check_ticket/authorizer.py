"""
Core authorization logic for Check Ticket Lambda Authorizer.

Parses strict Authorization header format, looks up ticket in DynamoDB,
validates expiration and secret hash, and generates API Gateway IAM Allow policies.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import boto3
import ulid
from mint_ticket.issuer import verify_secret

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Base64URL character set without padding
BASE64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_authorization_header(auth_header: str | None) -> tuple[str, str]:
    """
    Parse and validate the HTTP Authorization header.

    Format contract: Strictly 'Ticket <ticket_id>:<secret>'
    - Scheme: Strictly 'Ticket' (case-sensitive) followed by a single space.
    - Credentials: '<ticket_id>:<secret>' delimited by the first colon.
    - ticket_id: 26-character canonical Crockford Base32 ULID.
    - secret: non-empty base64url string without padding.

    Raises:
        Exception("Unauthorized"): If header is missing, malformed, or invalid.
    """
    if not isinstance(auth_header, str) or not auth_header:
        raise Exception("Unauthorized")

    if not auth_header.startswith("Ticket "):
        raise Exception("Unauthorized")

    credentials = auth_header[len("Ticket "):]
    if ":" not in credentials:
        raise Exception("Unauthorized")

    ticket_id, secret = credentials.split(":", 1)

    # Validate ticket_id: exactly 26 chars, valid ULID
    if len(ticket_id) != 26:
        raise Exception("Unauthorized")

    try:
        ulid.ULID.from_str(ticket_id)
    except Exception:  # noqa: BLE001
        raise Exception("Unauthorized")

    # Validate secret: non-empty, no padding '=', valid base64url characters
    if not secret or "=" in secret or not BASE64URL_PATTERN.match(secret):
        raise Exception("Unauthorized")

    return ticket_id, secret


def generate_stage_wildcard_arn(method_arn: str) -> str:
    """
    Transform an API Gateway methodArn into a wildcard stage ARN for caching.

    Example:
        arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status
        -> arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/*/*
    """
    if "/" in method_arn:
        arn_prefix, stage_and_rest = method_arn.split("/", 1)
        stage = stage_and_rest.split("/")[0]
        return f"{arn_prefix}/{stage}/*/*"
    return method_arn


def build_allow_policy(ticket_id: str, resource_arn: str) -> dict[str, Any]:
    """Construct an API Gateway IAM Allow policy document and authorizer context."""
    return {
        "principalId": f"ticket:{ticket_id}",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": resource_arn,
                }
            ],
        },
        "context": {
            "ticketId": ticket_id,
        },
    }


def authorize_ticket(
    table_name: str,
    auth_header: str | None,
    method_arn: str,
    dynamodb_client: Any = None,
    current_time: float | None = None,
) -> dict[str, Any]:
    """
    Verify ticket credentials against DynamoDB and return an IAM policy.

    Raises:
        Exception("Unauthorized"): On any authentication failure or error.
    """
    if not table_name or not method_arn:
        raise Exception("Unauthorized")

    ticket_id, secret = parse_authorization_header(auth_header)

    logger.info("Authorizing ticket %s", ticket_id)

    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")

    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={"ticket_id": {"S": ticket_id}},
            ProjectionExpression="#tid, #sh, #exp, #js",
            ExpressionAttributeNames={
                "#tid": "ticket_id",
                "#sh": "secret_hash",
                "#exp": "expires_at",
                "#js": "job_status",
            },
        )
    except Exception as exc:
        logger.error("DynamoDB lookup failed for ticket %s: %s", ticket_id, exc)
        raise Exception("Unauthorized") from exc

    item = response.get("Item")
    if not item:
        logger.info("Ticket %s not found in table", ticket_id)
        raise Exception("Unauthorized")

    # Expiration check
    if "expires_at" not in item or "N" not in item["expires_at"]:
        logger.warning("Ticket %s missing expires_at attribute", ticket_id)
        raise Exception("Unauthorized")

    try:
        expires_at = float(item["expires_at"]["N"])
    except (ValueError, TypeError):
        raise Exception("Unauthorized")

    now = current_time if current_time is not None else datetime.now(UTC).timestamp()
    if now >= expires_at:
        logger.info("Ticket %s expired at %s (current: %s)", ticket_id, expires_at, now)
        raise Exception("Unauthorized")

    # Secret hash verification
    if "secret_hash" not in item or "S" not in item["secret_hash"]:
        logger.warning("Ticket %s missing secret_hash attribute", ticket_id)
        raise Exception("Unauthorized")

    stored_secret_hash = item["secret_hash"]["S"]
    if not verify_secret(secret, stored_secret_hash):
        logger.info("Secret verification failed for ticket %s", ticket_id)
        raise Exception("Unauthorized")

    logger.info("Ticket %s successfully authorized", ticket_id)
    wildcard_arn = generate_stage_wildcard_arn(method_arn)
    return build_allow_policy(ticket_id, wildcard_arn)
