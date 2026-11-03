import base64
import hashlib
from unittest.mock import MagicMock, patch

import pytest
import ulid
from botocore.exceptions import ClientError

from check_ticket.authorizer import (
    authorize_ticket,
    build_allow_policy,
    generate_stage_wildcard_arn,
    parse_authorization_header,
)


class FakeDynamoDBClient:
    """In-memory fake DynamoDB client for get_item."""

    def __init__(self, item: dict | None = None, should_fail: Exception | None = None) -> None:
        self.item = item
        self.should_fail = should_fail
        self.calls: list[dict] = []

    def get_item(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.should_fail:
            raise self.should_fail
        if self.item is not None:
            return {"Item": self.item}
        return {}


def create_test_ticket_data() -> tuple[str, str, str]:
    """Generate a valid ticket ULID, raw base64url secret, and SHA-256 hash."""
    ticket_id = str(ulid.ULID())
    raw_bytes = b"01234567890123456789012345678901"
    secret = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")
    secret_hash = hashlib.sha256(raw_bytes).hexdigest()
    return ticket_id, secret, secret_hash


def test_parse_authorization_header_valid():
    ticket_id, secret, _ = create_test_ticket_data()
    header = f"Ticket {ticket_id}:{secret}"

    parsed_id, parsed_secret = parse_authorization_header(header)
    assert parsed_id == ticket_id
    assert parsed_secret == secret


@pytest.mark.parametrize(
    "invalid_header",
    [
        None,
        "",
        "   ",
        123,
        "Bearer some-token",
        "ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:secret",  # Lowercase scheme rejected
        "Ticket:01ARZ3NDEKTSV4RRFFQ69G5FAV:secret",  # Missing space
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV",  # Missing colon
        "Ticket :secret",  # Empty ticket ID
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FA:secret",  # 25 chars (too short)
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAVV:secret",  # 27 chars (too long)
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAU:secret",  # 'U' is not in Crockford Base32
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:",  # Empty secret
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:abc=def",  # Padding '=' forbidden
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:abc def",  # Whitespace in secret
        "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:abc+def",  # '+' is standard b64, not base64url
    ],
)
def test_parse_authorization_header_invalid(invalid_header):
    with pytest.raises(Exception, match="^Unauthorized$"):
        parse_authorization_header(invalid_header)


def test_generate_stage_wildcard_arn():
    method_arn = "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status"
    expected = "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/*/*"
    assert generate_stage_wildcard_arn(method_arn) == expected

    # Deep route
    deep_arn = "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/prod/POST/reports/generate"
    expected_deep = "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/prod/*/*"
    assert generate_stage_wildcard_arn(deep_arn) == expected_deep

    # Fallback when no slash
    assert generate_stage_wildcard_arn("wildcard-only") == "wildcard-only"


def test_build_allow_policy():
    ticket_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    arn = "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/*/*"
    policy = build_allow_policy(ticket_id, arn)

    assert policy["principalId"] == f"ticket:{ticket_id}"
    assert policy["context"] == {"ticketId": ticket_id}
    statement = policy["policyDocument"]["Statement"][0]
    assert statement["Action"] == "execute-api:Invoke"
    assert statement["Effect"] == "Allow"
    assert statement["Resource"] == arn


def test_authorize_ticket_success():
    ticket_id, secret, secret_hash = create_test_ticket_data()
    expires_at = 2_000_000_000  # Far in the future
    current_time = 1_700_000_000

    item = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
        "expires_at": {"N": str(expires_at)},
        "job_status": {"S": "issued"},
    }
    client = FakeDynamoDBClient(item=item)

    method_arn = "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status"
    auth_header = f"Ticket {ticket_id}:{secret}"

    policy = authorize_ticket(
        table_name="test-tickets",
        auth_header=auth_header,
        method_arn=method_arn,
        dynamodb_client=client,
        current_time=current_time,
    )

    assert policy["principalId"] == f"ticket:{ticket_id}"
    assert policy["context"]["ticketId"] == ticket_id
    assert policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    assert (
        policy["policyDocument"]["Statement"][0]["Resource"]
        == "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/*/*"
    )
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["TableName"] == "test-tickets"
    assert call["Key"]["ticket_id"]["S"] == ticket_id


def test_authorize_ticket_missing_table_or_arn():
    ticket_id, secret, _ = create_test_ticket_data()
    header = f"Ticket {ticket_id}:{secret}"

    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(table_name="", auth_header=header, method_arn="arn:aws:...")

    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(table_name="test-table", auth_header=header, method_arn="")


def test_authorize_ticket_not_found():
    ticket_id, secret, _ = create_test_ticket_data()
    client = FakeDynamoDBClient(item=None)

    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(
            table_name="test-tickets",
            auth_header=f"Ticket {ticket_id}:{secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
            dynamodb_client=client,
        )


def test_authorize_ticket_expired():
    ticket_id, secret, secret_hash = create_test_ticket_data()
    expires_at = 1_700_000_000
    current_time = 1_700_000_001  # After expiration

    item = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
        "expires_at": {"N": str(expires_at)},
    }
    client = FakeDynamoDBClient(item=item)

    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(
            table_name="test-tickets",
            auth_header=f"Ticket {ticket_id}:{secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
            dynamodb_client=client,
            current_time=current_time,
        )


def test_authorize_ticket_missing_or_invalid_expires_at():
    ticket_id, secret, secret_hash = create_test_ticket_data()

    # Missing expires_at
    item_missing = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
    }
    client_missing = FakeDynamoDBClient(item=item_missing)
    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(
            table_name="test-tickets",
            auth_header=f"Ticket {ticket_id}:{secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
            dynamodb_client=client_missing,
        )

    # Invalid numeric value
    item_invalid = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
        "expires_at": {"N": "not-a-number"},
    }
    client_invalid = FakeDynamoDBClient(item=item_invalid)
    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(
            table_name="test-tickets",
            auth_header=f"Ticket {ticket_id}:{secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
            dynamodb_client=client_invalid,
        )


def test_authorize_ticket_secret_mismatch():
    ticket_id, secret, secret_hash = create_test_ticket_data()
    expires_at = 2_000_000_000

    item = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
        "expires_at": {"N": str(expires_at)},
    }
    client = FakeDynamoDBClient(item=item)

    # Present mismatched secret
    wrong_secret = secret[:-1] + ("A" if secret[-1] != "A" else "B")

    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(
            table_name="test-tickets",
            auth_header=f"Ticket {ticket_id}:{wrong_secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
            dynamodb_client=client,
        )


def test_authorize_ticket_missing_secret_hash_attr():
    ticket_id, secret, _ = create_test_ticket_data()
    expires_at = 2_000_000_000

    item = {
        "ticket_id": {"S": ticket_id},
        "expires_at": {"N": str(expires_at)},
    }
    client = FakeDynamoDBClient(item=item)

    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(
            table_name="test-tickets",
            auth_header=f"Ticket {ticket_id}:{secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
            dynamodb_client=client,
        )


def test_authorize_ticket_dynamodb_client_error():
    ticket_id, secret, _ = create_test_ticket_data()
    err = ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "GetItem")
    client = FakeDynamoDBClient(should_fail=err)

    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize_ticket(
            table_name="test-tickets",
            auth_header=f"Ticket {ticket_id}:{secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
            dynamodb_client=client,
        )


def test_authorize_ticket_default_dynamodb_client():
    ticket_id, secret, secret_hash = create_test_ticket_data()
    expires_at = 2_000_000_000

    with patch("boto3.client") as mock_boto:
        mock_instance = MagicMock()
        mock_instance.get_item.return_value = {
            "Item": {
                "ticket_id": {"S": ticket_id},
                "secret_hash": {"S": secret_hash},
                "expires_at": {"N": str(expires_at)},
            }
        }
        mock_boto.return_value = mock_instance

        policy = authorize_ticket(
            table_name="default-client-table",
            auth_header=f"Ticket {ticket_id}:{secret}",
            method_arn="arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/status",
        )

        mock_boto.assert_called_once_with("dynamodb")
        assert policy["principalId"] == f"ticket:{ticket_id}"
