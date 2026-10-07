"""Unit tests for Submit CLI."""

import json
from unittest.mock import patch

from submit.cli import main


def test_cli_missing_args(capsys, monkeypatch):
    monkeypatch.delenv("TICKETS_TABLE_NAME", raising=False)
    monkeypatch.delenv("UPLOADS_BUCKET_NAME", raising=False)

    rc = main([])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Error: --table-name or TICKETS_TABLE_NAME" in captured.err

    rc2 = main(["--table-name", "tickets"])
    assert rc2 == 1
    captured2 = capsys.readouterr()
    assert "Error: --bucket-name or UPLOADS_BUCKET_NAME" in captured2.err


def test_cli_missing_files_input(capsys, monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "tickets")
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "bucket")
    # stdin is atty
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    rc = main([])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Error: --files argument or stdin" in captured.err


def test_cli_invalid_json(capsys, monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "tickets")
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "bucket")

    rc = main(["--files", "invalid-json"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Error parsing JSON input" in captured.err


def test_cli_invalid_payload_type(capsys, monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "tickets")
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "bucket")

    rc = main(["--files", '"string-not-dict"'])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Error: payload must be a JSON object or array" in captured.err


def test_cli_success(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "tickets")
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "bucket")

    # Mock handler
    mock_resp = {
        "statusCode": 200,
        "headers": {},
        "body": json.dumps({"ticketId": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "expectedFileCount": 1}),
    }
    with patch("submit.cli.handler", return_value=mock_resp):
        # Test with direct json string
        payload = [{"filename": "doc.pdf", "fileSizeBytes": 2_000_000}]
        rc = main(["--files", json.dumps(payload)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "01ARZ3NDEKTSV4RRFFQ69G5FAV" in captured.out

        # Test with file path
        fpath = tmp_path / "files.json"
        fpath.write_text(json.dumps(payload))
        rc2 = main(["--files", str(fpath)])
        assert rc2 == 0

        # Test with stdin
        import io

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        rc3 = main([])
        assert rc3 == 0


def test_cli_handler_error(capsys, monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "tickets")
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "bucket")

    mock_resp = {
        "statusCode": 400,
        "headers": {},
        "body": json.dumps({"error": "Bad request"}),
    }
    with patch("submit.cli.handler", return_value=mock_resp):
        rc = main(["--files", json.dumps({"files": []})])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Error (400)" in captured.err
