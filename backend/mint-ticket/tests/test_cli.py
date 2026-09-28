import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from mint_ticket.cli import main


def test_cli_success_with_table_name_flag(capsys) -> None:
    fake_ticket = {"ticket_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "secret": "abc123secret"}

    with patch("mint_ticket.cli.mint_ticket", return_value=fake_ticket) as mock_mint:
        main(["--table-name", "my-dynamo-table"])

        mock_mint.assert_called_once_with(table_name="my-dynamo-table", ttl_seconds=86_400)
        captured = capsys.readouterr()
        assert captured.err == ""
        parsed_out = json.loads(captured.out)
        assert parsed_out == fake_ticket


def test_cli_success_with_tickets_table_name_env(monkeypatch, capsys) -> None:
    fake_ticket = {"ticket_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "secret": "abc123secret"}
    monkeypatch.setenv("TICKETS_TABLE_NAME", "env-tickets-table")
    monkeypatch.delenv("DYNAMODB_TABLE_NAME", raising=False)

    with patch("mint_ticket.cli.mint_ticket", return_value=fake_ticket) as mock_mint:
        main([])

        mock_mint.assert_called_once_with(table_name="env-tickets-table", ttl_seconds=86_400)
        captured = capsys.readouterr()
        parsed_out = json.loads(captured.out)
        assert parsed_out == fake_ticket


def test_cli_success_with_dynamodb_table_name_env(monkeypatch, capsys) -> None:
    fake_ticket = {"ticket_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "secret": "abc123secret"}
    monkeypatch.delenv("TICKETS_TABLE_NAME", raising=False)
    monkeypatch.setenv("DYNAMODB_TABLE_NAME", "fallback-dynamo-table")

    with patch("mint_ticket.cli.mint_ticket", return_value=fake_ticket) as mock_mint:
        main([])

        mock_mint.assert_called_once_with(table_name="fallback-dynamo-table", ttl_seconds=86_400)
        captured = capsys.readouterr()
        parsed_out = json.loads(captured.out)
        assert parsed_out == fake_ticket


def test_cli_custom_ttl(capsys) -> None:
    fake_ticket = {"ticket_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "secret": "abc123secret"}

    with patch("mint_ticket.cli.mint_ticket", return_value=fake_ticket) as mock_mint:
        main(["--table-name", "custom-table", "--ttl-seconds", "3600"])

        mock_mint.assert_called_once_with(table_name="custom-table", ttl_seconds=3600)
        captured = capsys.readouterr()
        assert captured.err == ""
        parsed_out = json.loads(captured.out)
        assert parsed_out == fake_ticket


def test_cli_missing_table_exits_with_error(monkeypatch, capsys) -> None:
    monkeypatch.delenv("TICKETS_TABLE_NAME", raising=False)
    monkeypatch.delenv("DYNAMODB_TABLE_NAME", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "Error: DynamoDB table name must be specified via --table-name flag" in captured.err
    assert captured.out == ""


def test_cli_runtime_exception_exits_with_structured_error(capsys) -> None:
    client_error = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Collision"}},
        "PutItem",
    )

    with patch("mint_ticket.cli.mint_ticket", side_effect=client_error):
        with pytest.raises(SystemExit) as exc_info:
            main(["--table-name", "test-table"])

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "Error: An error occurred (ConditionalCheckFailedException)" in captured.err
        assert captured.out == ""


def test_cli_end_to_end_execution(capsys) -> None:
    with patch("boto3.client") as mock_boto:
        mock_instance = MagicMock()
        mock_boto.return_value = mock_instance

        main(["--table-name", "e2e-table"])

        captured = capsys.readouterr()
        assert captured.err == ""
        parsed_out = json.loads(captured.out)
        assert "ticket_id" in parsed_out
        assert "secret" in parsed_out
        assert len(parsed_out["ticket_id"]) == 26


def test_cli_module_execution() -> None:
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "mint_ticket.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ticket-issuer" in result.stdout
    assert "--table-name" in result.stdout


def test_cli_old_table_flag_rejected(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--table", "legacy-table"])

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "unrecognized arguments: --table" in captured.err
