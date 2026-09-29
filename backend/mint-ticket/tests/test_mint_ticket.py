import base64
import hashlib
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import ulid
from botocore.exceptions import ClientError

from mint_ticket import mint_ticket


class FakeDynamoDBClient:
    """In-memory fake DynamoDB client for capturing put_item calls."""

    def __init__(self, should_fail: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.should_fail = should_fail

    def put_item(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.should_fail:
            raise self.should_fail
        return {}


def decode_unpadded_base64url(secret_str: str) -> bytes:
    padding = b"=" * (-len(secret_str) % 4)
    return base64.urlsafe_b64decode(secret_str.encode("ascii") + padding)


def test_mint_ticket_success_structure_and_persistence() -> None:
    client = FakeDynamoDBClient()
    table_name = "test-tickets"

    result = mint_ticket(table_name=table_name, dynamodb_client=client)

    # 1. Output structure
    assert isinstance(result, dict)
    assert "ticket_id" in result
    assert "secret" in result

    ticket_id = result["ticket_id"]
    secret = result["secret"]

    # Canonical ULID length and parseability
    assert len(ticket_id) == 26
    parsed_ulid = ulid.ULID.from_str(ticket_id)
    assert str(parsed_ulid) == ticket_id

    # Secret is non-empty base64url string without padding
    assert len(secret) > 0
    assert "=" not in secret
    secret_bytes = decode_unpadded_base64url(secret)
    assert len(secret_bytes) == 32

    # 2. DynamoDB put_item call assertions
    assert len(client.calls) == 1
    call = client.calls[0]

    assert call["TableName"] == table_name
    assert call["ConditionExpression"] == "attribute_not_exists(ticket_id)"

    item = call["Item"]
    assert item["ticket_id"] == {"S": ticket_id}
    assert item["job_status"] == {"S": "issued"}
    assert "expires_at" in item
    assert "N" in item["expires_at"]
    assert "created_at" in item
    assert "S" in item["created_at"]

    # Verify created_at is valid ISO 8601 UTC
    created_dt = datetime.fromisoformat(item["created_at"]["S"])
    assert created_dt.tzinfo is not None


def test_mint_ticket_secret_persistence_safety() -> None:
    client = FakeDynamoDBClient()
    table_name = "security-test-table"

    result = mint_ticket(table_name=table_name, dynamodb_client=client)
    secret = result["secret"]
    secret_bytes = decode_unpadded_base64url(secret)

    item = client.calls[0]["Item"]

    # Stored secret_hash matches sha256 of raw secret
    expected_hash = hashlib.sha256(secret_bytes).hexdigest()
    assert item["secret_hash"] == {"S": expected_hash}

    # Raw secret must never be persisted in any attribute
    assert "secret" not in item
    for attr_name, attr_val in item.items():
        assert attr_name != "secret"
        for val in attr_val.values():
            assert secret not in str(val)
            assert str(secret_bytes) not in str(val)


def test_mint_ticket_ttl_calculation() -> None:
    client = FakeDynamoDBClient()
    ttl_seconds = 60

    before = int(time.time())
    mint_ticket(table_name="ttl-table", ttl_seconds=ttl_seconds, dynamodb_client=client)
    after = int(time.time())

    item = client.calls[0]["Item"]
    expires_at = int(item["expires_at"]["N"])

    assert before + ttl_seconds <= expires_at <= after + ttl_seconds


def test_mint_ticket_conditional_write_failure_raises() -> None:
    client_error = ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "The conditional request failed",
            }
        },
        "PutItem",
    )
    client = FakeDynamoDBClient(should_fail=client_error)

    with pytest.raises(ClientError) as exc_info:
        mint_ticket(table_name="failure-table", dynamodb_client=client)

    assert exc_info.value.response["Error"]["Code"] == "ConditionalCheckFailedException"
    assert len(client.calls) == 1


def test_mint_ticket_uniqueness_and_consistency() -> None:
    client = FakeDynamoDBClient()

    result1 = mint_ticket(table_name="unique-table", dynamodb_client=client)
    result2 = mint_ticket(table_name="unique-table", dynamodb_client=client)

    assert result1["ticket_id"] != result2["ticket_id"]
    assert result1["secret"] != result2["secret"]

    assert len(client.calls) == 2
    assert client.calls[0]["Item"]["ticket_id"]["S"] == result1["ticket_id"]
    assert client.calls[1]["Item"]["ticket_id"]["S"] == result2["ticket_id"]


def test_mint_ticket_validation() -> None:
    client = FakeDynamoDBClient()

    with pytest.raises(ValueError, match="table_name is required"):
        mint_ticket(table_name="", dynamodb_client=client)

    with pytest.raises(ValueError, match="ttl_seconds must be non-negative"):
        mint_ticket(table_name="valid-table", ttl_seconds=-1, dynamodb_client=client)


def test_mint_ticket_default_dynamodb_client() -> None:
    with patch("boto3.client") as mock_boto_client:
        mock_instance = MagicMock()
        mock_boto_client.return_value = mock_instance

        res = mint_ticket(table_name="default-client-table")

        mock_boto_client.assert_called_once_with("dynamodb")
        mock_instance.put_item.assert_called_once()
        assert res["ticket_id"] == mock_instance.put_item.call_args.kwargs["Item"]["ticket_id"]["S"]
