"""
API Gateway Custom Lambda Authorizer entrypoint.

Extracts authorization headers and method ARN from either Token or Request
authorizer event payloads and calls authorize_ticket.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

from check_ticket.authorizer import authorize_ticket

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def get_dynamodb_client() -> Any:
    """Factory for DynamoDB low-level client."""
    return boto3.client("dynamodb")


def extract_auth_header(event: dict[str, Any]) -> str | None:
    """Extract Authorization header from Token or Request authorizer events."""
    if not isinstance(event, dict):
        return None

    # Token authorizer shape
    if "authorizationToken" in event:
        token = event.get("authorizationToken")
        return token if isinstance(token, str) else None

    # Request authorizer shape
    if "headers" in event and isinstance(event.get("headers"), dict):
        headers = event["headers"]
        token = headers.get("Authorization") or headers.get("authorization")
        return token if isinstance(token, str) else None

    # Convenience/direct invocation fallbacks
    for key in ("Authorization", "authorization", "auth_header"):
        if key in event and isinstance(event[key], str):
            return event[key]

    return None


def handler(
    event: dict[str, Any],
    context: Any = None,
    dynamodb_client: Any = None,
) -> dict[str, Any]:
    """
    AWS Lambda entrypoint for API Gateway custom authorizer.

    Returns:
        API Gateway IAM policy dict with Allow effect and ticket context.

    Raises:
        Exception("Unauthorized"): On any authentication failure.
    """
    table_name = os.environ.get("TICKETS_TABLE_NAME") or os.environ.get("DYNAMODB_TABLE_NAME")
    if not table_name:
        logger.error("TICKETS_TABLE_NAME environment variable is not configured")
        raise Exception("Unauthorized")

    if not isinstance(event, dict):
        logger.error("Invalid authorizer event format: expected dictionary")
        raise Exception("Unauthorized")

    auth_header = extract_auth_header(event)
    method_arn = event.get("methodArn") or event.get("method_arn")

    if not method_arn or not isinstance(method_arn, str):
        logger.error("Missing or invalid methodArn in authorizer event")
        raise Exception("Unauthorized")

    if dynamodb_client is None:
        dynamodb_client = get_dynamodb_client()

    return authorize_ticket(
        table_name=table_name,
        auth_header=auth_header,
        method_arn=method_arn,
        dynamodb_client=dynamodb_client,
    )
