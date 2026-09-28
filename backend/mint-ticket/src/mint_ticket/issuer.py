import base64
import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

import boto3
import ulid


def mint_ticket(
    table_name: str,
    ttl_seconds: int = 86_400,
    dynamodb_client: Any = None,
) -> dict[str, str]:
    """
    Mint a ticket and secret, persist the secret hash, and return the credential.

    Returns:
        {
            "ticket_id": str,   # ULID, safe to log and expose
            "secret":    str,   # raw bearer secret, base64url without padding, returned ONCE
        }
    """
    if not table_name:
        raise ValueError("table_name is required")
    if ttl_seconds < 0:
        raise ValueError("ttl_seconds must be non-negative")

    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")

    # 1. Ticket ID — 26-char canonical ULID
    ticket_id = str(ulid.ULID())

    # 2. Secret — 32 bytes from CSPRNG, base64url without padding
    raw_secret_bytes = secrets.token_bytes(32)
    secret = base64.urlsafe_b64encode(raw_secret_bytes).rstrip(b"=").decode("ascii")

    # 3. Hash — SHA-256 of raw secret bytes stored as hex digest
    secret_hash = hashlib.sha256(raw_secret_bytes).hexdigest()

    # 4. Timestamps
    now = datetime.now(UTC)
    expires_at = int(now.timestamp()) + ttl_seconds
    now_iso_utc = now.isoformat()

    # 5. Persist to DynamoDB via low-level client
    item = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
        "status": {"S": "issued"},
        "expires_at": {"N": str(expires_at)},
        "created_at": {"S": now_iso_utc},
    }

    dynamodb_client.put_item(
        TableName=table_name,
        Item=item,
        ConditionExpression="attribute_not_exists(ticket_id)",
    )

    # 6. Return credential dict
    return {
        "ticket_id": ticket_id,
        "secret": secret,
    }
