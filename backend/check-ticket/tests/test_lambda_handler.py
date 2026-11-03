import base64
import hashlib
from unittest.mock import MagicMock, patch

import pytest
import ulid

from check_ticket.lambda_handler import extract_auth_header, handler


class FakeDynamoDBClient:
    """In-memory fake DynamoDB client for handler tests."""

    def __init__(self, item: dict | None = None) -> None:
        self.item = item

    def get_item(self, **kwargs) -> dict:
        if self.item is not None:
            return {"Item": self.item}
        return {}


def create_test_ticket_data() -> tuple[str, str, str]:
    ticket_id = str(ulid.ULID())
    raw_bytes = b"98765432109876543210987654321098"
    secret = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")
    secret_hash = hashlib.sha256(raw_bytes).hexdigest()
    return ticket_id, secret, secret_hash


def test_extract_auth_header_various_shapes():
    # Token authorizer
    token_event = {"authorizationToken": "Ticket 123:abc"}
    assert extract_auth_header(token_event) == "Ticket 123:abc"

    # Request authorizer (standard capitalization)
    req_event = {"headers": {"Authorization": "Ticket 456:def"}}
    assert extract_auth_header(req_event) == "Ticket 456:def"

    # Request authorizer (lowercase)
    req_lower_event = {"headers": {"authorization": "Ticket 789:ghi"}}
    assert extract_auth_header(req_lower_event) == "Ticket 789:ghi"

    # Direct invocation fallbacks
    assert extract_auth_header({"Authorization": "Ticket direct:1"}) == "Ticket direct:1"
    assert extract_auth_header({"authorization": "Ticket direct:2"}) == "Ticket direct:2"
    assert extract_auth_header({"auth_header": "Ticket direct:3"}) == "Ticket direct:3"

    # Invalid / empty
    assert extract_auth_header({}) is None
    assert extract_auth_header({"headers": {}}) is None
    assert extract_auth_header("not-a-dict") is None  # type: ignore[arg-type]


def test_handler_success_token_authorizer(monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")
    ticket_id, secret, secret_hash = create_test_ticket_data()

    item = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
        "expires_at": {"N": "2500000000"},
        "job_status": {"S": "issued"},
    }
    client = FakeDynamoDBClient(item=item)

    event = {
        "type": "TOKEN",
        "authorizationToken": f"Ticket {ticket_id}:{secret}",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status",
    }

    result = handler(event, dynamodb_client=client)

    assert result["principalId"] == f"ticket:{ticket_id}"
    assert result["context"]["ticketId"] == ticket_id
    assert result["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    assert (
        result["policyDocument"]["Statement"][0]["Resource"]
        == "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/*/*"
    )


def test_handler_success_request_authorizer(monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")
    ticket_id, secret, secret_hash = create_test_ticket_data()

    item = {
        "ticket_id": {"S": ticket_id},
        "secret_hash": {"S": secret_hash},
        "expires_at": {"N": "2500000000"},
    }
    client = FakeDynamoDBClient(item=item)

    event = {
        "type": "REQUEST",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report",
        "headers": {
            "Authorization": f"Ticket {ticket_id}:{secret}",
        },
    }

    result = handler(event, dynamodb_client=client)
    assert result["principalId"] == f"ticket:{ticket_id}"


def test_handler_missing_table_env(monkeypatch):
    monkeypatch.delenv("TICKETS_TABLE_NAME", raising=False)
    monkeypatch.delenv("DYNAMODB_TABLE_NAME", raising=False)

    event = {
        "authorizationToken": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:secret",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status",
    }

    with pytest.raises(Exception, match="^Unauthorized$"):
        handler(event)


def test_handler_missing_method_arn(monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")
    event = {
        "authorizationToken": "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:secret",
    }

    with pytest.raises(Exception, match="^Unauthorized$"):
        handler(event)


def test_handler_invalid_event_type(monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")

    with pytest.raises(Exception, match="^Unauthorized$"):
        handler("not-a-dict")  # type: ignore[arg-type]


def test_handler_default_client_factory(monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")
    ticket_id, secret, secret_hash = create_test_ticket_data()

    with patch("check_ticket.lambda_handler.get_dynamodb_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_item.return_value = {
            "Item": {
                "ticket_id": {"S": ticket_id},
                "secret_hash": {"S": secret_hash},
                "expires_at": {"N": "2500000000"},
            }
        }
        mock_get_client.return_value = mock_client

        event = {
            "authorizationToken": f"Ticket {ticket_id}:{secret}",
            "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/dev/GET/pii-report-status",
        }

        result = handler(event)
        mock_get_client.assert_called_once()
        assert result["principalId"] == f"ticket:{ticket_id}"


def test_get_dynamodb_client_real_factory():
    with patch("boto3.client") as mock_boto_client:
        mock_instance = MagicMock()
        mock_boto_client.return_value = mock_instance
        from check_ticket.lambda_handler import get_dynamodb_client

        client = get_dynamodb_client()
        mock_boto_client.assert_called_once_with("dynamodb")
        assert client is mock_instance
