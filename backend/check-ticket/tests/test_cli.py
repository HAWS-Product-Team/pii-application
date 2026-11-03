import base64
import hashlib
import io
import json
from unittest.mock import patch

import ulid

from check_ticket.cli import main


class FakeDynamoDBClient:
    """Fake DynamoDB client for CLI tests."""

    def __init__(self, item: dict | None = None) -> None:
        self.item = item

    def get_item(self, **kwargs) -> dict:
        if self.item is not None:
            return {"Item": self.item}
        return {}


def create_test_ticket_data() -> tuple[str, str, str]:
    ticket_id = str(ulid.ULID())
    raw_bytes = b"abcdefabcdefabcdefabcdefabcdefab"
    secret = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")
    secret_hash = hashlib.sha256(raw_bytes).hexdigest()
    return ticket_id, secret, secret_hash


def setup_mock_dynamo(ticket_id: str, secret_hash: str):
    client = FakeDynamoDBClient(
        item={
            "ticket_id": {"S": ticket_id},
            "secret_hash": {"S": secret_hash},
            "expires_at": {"N": "2500000000"},
            "job_status": {"S": "issued"},
        }
    )
    return patch("check_ticket.lambda_handler.get_dynamodb_client", return_value=client)


def test_cli_missing_table_name(monkeypatch, capsys):
    monkeypatch.delenv("TICKETS_TABLE_NAME", raising=False)
    monkeypatch.delenv("DYNAMODB_TABLE_NAME", raising=False)

    exit_code = main(["--auth-header", "Ticket 01ARZ3NDEKTSV4RRFFQ69G5FAV:secret"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: --table-name or TICKETS_TABLE_NAME environment variable is required" in captured.err


def test_cli_success_auth_header(capsys):
    ticket_id, secret, secret_hash = create_test_ticket_data()

    with setup_mock_dynamo(ticket_id, secret_hash):
        exit_code = main(
            [
                "--table-name",
                "test-tickets",
                "--auth-header",
                f"Ticket {ticket_id}:{secret}",
            ]
        )

    assert exit_code == 0
    captured = capsys.readouterr()
    policy = json.loads(captured.out)
    assert policy["principalId"] == f"ticket:{ticket_id}"
    assert policy["context"]["ticketId"] == ticket_id


def test_cli_success_ticket_id_and_secret(capsys):
    ticket_id, secret, secret_hash = create_test_ticket_data()

    with setup_mock_dynamo(ticket_id, secret_hash):
        exit_code = main(
            [
                "--table-name",
                "test-tickets",
                "--ticket-id",
                ticket_id,
                "--secret",
                secret,
            ]
        )

    assert exit_code == 0
    captured = capsys.readouterr()
    policy = json.loads(captured.out)
    assert policy["principalId"] == f"ticket:{ticket_id}"


def test_cli_partial_ticket_id_or_secret(capsys):
    exit_code = main(["--table-name", "test-tickets", "--ticket-id", "01ARZ3NDEKTSV4RRFFQ69G5FAV"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Both --ticket-id and --secret must be provided together" in captured.err


def test_cli_success_event_json_string(capsys):
    ticket_id, secret, secret_hash = create_test_ticket_data()
    event = {
        "authorizationToken": f"Ticket {ticket_id}:{secret}",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/prod/GET/pii-report",
    }

    with setup_mock_dynamo(ticket_id, secret_hash):
        exit_code = main(
            [
                "--table-name",
                "test-tickets",
                "--event",
                json.dumps(event),
            ]
        )

    assert exit_code == 0
    captured = capsys.readouterr()
    policy = json.loads(captured.out)
    assert (
        policy["policyDocument"]["Statement"][0]["Resource"]
        == "arn:aws:execute-api:us-east-1:123456789012:5m782q7f45/prod/*/*"
    )


def test_cli_success_event_file(tmp_path, capsys):
    ticket_id, secret, secret_hash = create_test_ticket_data()
    event_file = tmp_path / "event.json"
    event = {
        "headers": {"Authorization": f"Ticket {ticket_id}:{secret}"},
    }
    event_file.write_text(json.dumps(event), encoding="utf-8")

    with setup_mock_dynamo(ticket_id, secret_hash):
        exit_code = main(
            [
                "--table-name",
                "test-tickets",
                "--event",
                str(event_file),
            ]
        )

    assert exit_code == 0
    captured = capsys.readouterr()
    policy = json.loads(captured.out)
    assert policy["principalId"] == f"ticket:{ticket_id}"


def test_cli_event_invalid_json(capsys):
    exit_code = main(["--table-name", "test-tickets", "--event", "invalid-json{"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error parsing event JSON" in captured.err


def test_cli_event_non_dict_json(capsys):
    exit_code = main(["--table-name", "test-tickets", "--event", "[1, 2, 3]"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Event payload must be a JSON object" in captured.err


def test_cli_stdin_raw_header(capsys):
    ticket_id, secret, secret_hash = create_test_ticket_data()

    with patch("sys.stdin", io.StringIO(f"Ticket {ticket_id}:{secret}")), patch(
        "sys.stdin.isatty", return_value=False
    ), setup_mock_dynamo(ticket_id, secret_hash):
        exit_code = main(["--table-name", "test-tickets"])

    assert exit_code == 0
    captured = capsys.readouterr()
    policy = json.loads(captured.out)
    assert policy["principalId"] == f"ticket:{ticket_id}"


def test_cli_stdin_json_event(capsys):
    ticket_id, secret, secret_hash = create_test_ticket_data()
    event = {"authorizationToken": f"Ticket {ticket_id}:{secret}"}

    with patch("sys.stdin", io.StringIO(json.dumps(event))), patch(
        "sys.stdin.isatty", return_value=False
    ), setup_mock_dynamo(ticket_id, secret_hash):
        exit_code = main(["--table-name", "test-tickets"])

    assert exit_code == 0
    captured = capsys.readouterr()
    policy = json.loads(captured.out)
    assert policy["principalId"] == f"ticket:{ticket_id}"


def test_cli_stdin_empty(capsys):
    with patch("sys.stdin", io.StringIO("   ")), patch("sys.stdin.isatty", return_value=False):
        exit_code = main(["--table-name", "test-tickets"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Empty input from stdin" in captured.err


def test_cli_missing_all_inputs_tty(capsys):
    with patch("sys.stdin.isatty", return_value=True):
        exit_code = main(["--table-name", "test-tickets"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Input credentials required" in captured.err


def test_cli_unauthorized_error(capsys):
    ticket_id, secret, _ = create_test_ticket_data()
    # Fake client with wrong hash
    client = FakeDynamoDBClient(
        item={
            "ticket_id": {"S": ticket_id},
            "secret_hash": {"S": "wrong_hash"},
            "expires_at": {"N": "2500000000"},
        }
    )

    with patch("check_ticket.lambda_handler.get_dynamodb_client", return_value=client):
        exit_code = main(
            [
                "--table-name",
                "test-tickets",
                "--auth-header",
                f"Ticket {ticket_id}:{secret}",
            ]
        )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Unauthorized" in captured.err
