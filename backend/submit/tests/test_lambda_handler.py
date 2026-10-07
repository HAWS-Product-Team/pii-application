"""Unit tests for Submit Lambda handler."""

import base64
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from submit.lambda_handler import (
    CORS_HEADERS,
    MAX_FILE_SIZE_BYTES,
    MIN_FILE_SIZE_BYTES,
    handler,
    validate_files,
)


@pytest.fixture
def mock_dynamodb():
    client = MagicMock()
    client.put_item.return_value = {}
    client.update_item.return_value = {}
    return client


@pytest.fixture
def mock_s3():
    client = MagicMock()
    client.generate_presigned_url.side_effect = lambda ClientMethod, Params, ExpiresIn: (
        f"https://s3.amazonaws.com/{Params['Bucket']}/{Params['Key']}?sig=test"
    )
    return client


@pytest.fixture
def default_env(monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "pii-uploads-test")
    monkeypatch.setenv("MAX_FILES", "20")
    monkeypatch.setenv("MAX_TOTAL_BYTES", str(4 * 1024 * 1024 * 1024))
    monkeypatch.setenv("PRESIGNED_EXPIRY_SECONDS", "900")
    monkeypatch.setenv("TICKET_TTL_SECONDS", "86400")


def test_cors_preflight_options():
    event = {"httpMethod": "OPTIONS"}
    resp = handler(event)
    assert resp["statusCode"] == 200
    assert resp["headers"] == CORS_HEADERS
    assert resp["body"] == ""

    # Test HTTP API v2 route OPTIONS
    event_v2 = {"requestContext": {"http": {"method": "OPTIONS"}}}
    resp_v2 = handler(event_v2)
    assert resp_v2["statusCode"] == 200


def test_missing_env_vars(monkeypatch, mock_dynamodb, mock_s3):
    monkeypatch.delenv("TICKETS_TABLE_NAME", raising=False)
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "pii-uploads-test")

    event = {"body": json.dumps({"files": [{"filename": "doc.pdf", "fileSizeBytes": 2_000_000}]})}
    resp = handler(event, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 500
    assert "Internal configuration error" in resp["body"]

    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")
    monkeypatch.delenv("UPLOADS_BUCKET_NAME", raising=False)
    resp = handler(event, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 500
    assert "Internal configuration error" in resp["body"]


def test_invalid_request_body_format(default_env, mock_dynamodb, mock_s3):
    # None body
    resp = handler({"body": None}, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 400
    assert "Missing request body" in resp["body"]

    # Invalid JSON string
    resp = handler({"body": "{invalid-json"}, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 400
    assert "Invalid JSON in request body" in resp["body"]

    # Invalid base64 body
    resp = handler(
        {"body": "???notbase64", "isBase64Encoded": True},
        dynamodb_client=mock_dynamodb,
        s3_client=mock_s3,
    )
    assert resp["statusCode"] == 400
    assert "Invalid base64-encoded body" in resp["body"]

    # Valid base64 body with invalid JSON
    b64_invalid_json = base64.b64encode(b"{bad").decode("ascii")
    resp = handler(
        {"body": b64_invalid_json, "isBase64Encoded": True},
        dynamodb_client=mock_dynamodb,
        s3_client=mock_s3,
    )
    assert resp["statusCode"] == 400
    assert "Invalid JSON in request body" in resp["body"]

    # Body is not dict or string
    resp = handler({"body": 12345}, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 400

    # Payload is a list, not object
    resp = handler(
        {"body": json.dumps([1, 2, 3])}, dynamodb_client=mock_dynamodb, s3_client=mock_s3
    )
    assert resp["statusCode"] == 400
    assert "Payload must be a JSON object" in resp["body"]

    # Event has no body and no files
    resp = handler({}, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 400
    assert "'files' is required" in resp["body"]


def test_validate_files_not_a_list():
    assert validate_files("not-a-list", 20, 1000) == "'files' field must be an array"
    assert validate_files([], 20, 1000) == "Batch 'files' list cannot be empty"


def test_validate_files_count_exceeded():
    files = [{"filename": f"file{i}.pdf", "fileSizeBytes": 2_000_000} for i in range(5)]
    err = validate_files(files, max_files=4, max_total_bytes=100_000_000)
    assert err == "Batch file count (5) exceeds maximum allowed (4)"


def test_validate_files_total_size_exceeded():
    files = [
        {"filename": "file1.pdf", "fileSizeBytes": 10_000_000},
        {"filename": "file2.pdf", "fileSizeBytes": 10_000_000},
    ]
    err = validate_files(files, max_files=5, max_total_bytes=15_000_000)
    assert err == "Batch total size (20000000 bytes) exceeds maximum allowed (15000000 bytes)"


def test_validate_files_item_not_dict():
    err = validate_files(["not-a-dict"], 5, 100_000_000)
    assert "must be a JSON object" in err


def test_validate_files_filename_checks():
    # Missing filename
    assert "Missing required 'filename'" in validate_files(
        [{"fileSizeBytes": 2_000_000}], 5, 100_000_000
    )

    # Empty filename
    assert "non-empty string" in validate_files(
        [{"filename": "", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )
    assert "non-empty string" in validate_files(
        [{"filename": "   ", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )

    # Path traversal
    assert "directory separators and path traversal" in validate_files(
        [{"filename": "../doc.pdf", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )
    assert "directory separators and path traversal" in validate_files(
        [{"filename": "sub/doc.pdf", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )
    assert "directory separators and path traversal" in validate_files(
        [{"filename": "sub\\doc.pdf", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )

    # Non-pdf
    assert "must have a .pdf extension" in validate_files(
        [{"filename": "doc.csv", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )

    # Characters before extension
    assert "must contain characters before extension" in validate_files(
        [{"filename": ".pdf", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )
    assert "must contain characters before extension" in validate_files(
        [{"filename": "   .pdf", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )

    # Unsafe characters
    assert "only alphanumeric characters" in validate_files(
        [{"filename": "doc;rm.pdf", "fileSizeBytes": 2_000_000}], 5, 100_000_000
    )


def test_validate_files_duplicate_filename():
    files = [
        {"filename": "Statement_Jan.pdf", "fileSizeBytes": 2_000_000},
        {"filename": "statement_jan.pdf", "fileSizeBytes": 3_000_000},
    ]
    err = validate_files(files, 5, 100_000_000)
    assert err == "Duplicate filename in batch: 'statement_jan.pdf'"


def test_validate_files_size_checks():
    # Missing size
    assert "Missing required 'fileSizeBytes'" in validate_files(
        [{"filename": "doc.pdf"}], 5, 100_000_000
    )

    # Non-int or bool size
    assert "must be an integer" in validate_files(
        [{"filename": "doc.pdf", "fileSizeBytes": True}], 5, 100_000_000
    )
    assert "must be an integer" in validate_files(
        [{"filename": "doc.pdf", "fileSizeBytes": "2000000"}], 5, 100_000_000
    )

    # Below 1 MB
    assert "is below minimum allowed" in validate_files(
        [{"filename": "doc.pdf", "fileSizeBytes": MIN_FILE_SIZE_BYTES - 1}], 5, 100_000_000
    )

    # Above 15 MB
    assert "exceeds maximum allowed" in validate_files(
        [{"filename": "doc.pdf", "fileSizeBytes": MAX_FILE_SIZE_BYTES + 1}], 5, 100_000_000
    )


def test_happy_path_with_proxy_event(default_env, mock_dynamodb, mock_s3):
    event = {
        "body": json.dumps(
            {
                "files": [
                    {"filename": "jan.pdf", "fileSizeBytes": 5_242_880},
                    {"filename": "feb.pdf", "fileSizeBytes": 3_145_728},
                ]
            }
        )
    }

    response = handler(event, dynamodb_client=mock_dynamodb, s3_client=mock_s3)

    assert response["statusCode"] == 200
    assert response["headers"] == CORS_HEADERS

    body = json.loads(response["body"])
    assert "ticketId" in body
    assert len(body["ticketId"]) == 26  # ULID length
    assert "secret" in body
    assert len(body["secret"]) > 20
    assert body["uploadPrefix"] == f"uploads/{body['ticketId']}/"
    assert body["expectedFileCount"] == 2
    assert body["expiresInSeconds"] == 900
    assert len(body["uploads"]) == 2

    # Check uploads contents
    u1 = body["uploads"][0]
    assert u1["filename"] == "jan.pdf"
    assert u1["key"] == f"uploads/{body['ticketId']}/jan.pdf"
    assert u1["uploadUrl"].startswith(f"https://s3.amazonaws.com/pii-uploads-test/{u1['key']}")

    u2 = body["uploads"][1]
    assert u2["filename"] == "feb.pdf"
    assert u2["key"] == f"uploads/{body['ticketId']}/feb.pdf"

    # Verify DynamoDB calls: put_item (via mint_ticket) + follow-up update_item
    assert mock_dynamodb.put_item.call_count == 1
    assert mock_dynamodb.update_item.call_count == 1
    update_call = mock_dynamodb.update_item.call_args[1]
    assert update_call["TableName"] == "pii-tickets-test"
    assert update_call["Key"] == {"ticket_id": {"S": body["ticketId"]}}
    assert update_call["ExpressionAttributeValues"][":new_status"] == {"S": "AWAITING_UPLOAD"}
    assert update_call["ExpressionAttributeValues"][":count"] == {"N": "2"}
    assert update_call["ExpressionAttributeNames"]["#count"] == "expected_file_count"
    assert update_call["ConditionExpression"] == "attribute_exists(ticket_id)"

    # Verify S3 presigned URL parameters: pinned ContentType = application/pdf
    assert mock_s3.generate_presigned_url.call_count == 2
    for call in mock_s3.generate_presigned_url.call_args_list:
        assert call[1]["ClientMethod"] == "put_object"
        assert call[1]["Params"]["Bucket"] == "pii-uploads-test"
        assert call[1]["Params"]["ContentType"] == "application/pdf"
        assert call[1]["ExpiresIn"] == 900


def test_happy_path_direct_event_and_base64(default_env, mock_dynamodb, mock_s3):
    payload = {"files": [{"filename": "statement.pdf", "fileSizeBytes": 2_000_000}]}

    # Direct invocation with payload dict
    resp1 = handler(payload, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp1["statusCode"] == 200

    # Base64 encoded proxy body
    b64_body = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    resp2 = handler(
        {"body": b64_body, "isBase64Encoded": True},
        dynamodb_client=mock_dynamodb,
        s3_client=mock_s3,
    )
    assert resp2["statusCode"] == 200

    # Direct dict in body
    resp3 = handler({"body": payload}, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp3["statusCode"] == 200


def test_dynamodb_mint_ticket_failure(default_env, mock_dynamodb, mock_s3):
    mock_dynamodb.put_item.side_effect = RuntimeError("DynamoDB put failure")
    event = {"body": json.dumps({"files": [{"filename": "doc.pdf", "fileSizeBytes": 2_000_000}]})}

    resp = handler(event, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 500
    assert "Failed to create ticket" in resp["body"]


def test_dynamodb_update_item_failure(default_env, mock_dynamodb, mock_s3):
    mock_dynamodb.update_item.side_effect = RuntimeError("DynamoDB update failure")
    event = {"body": json.dumps({"files": [{"filename": "doc.pdf", "fileSizeBytes": 2_000_000}]})}

    resp = handler(event, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 500
    assert "Failed to record ticket expectations" in resp["body"]


def test_s3_presign_failure(default_env, mock_dynamodb, mock_s3):
    mock_s3.generate_presigned_url.side_effect = RuntimeError("S3 presign failure")
    event = {"body": json.dumps({"files": [{"filename": "doc.pdf", "fileSizeBytes": 2_000_000}]})}

    resp = handler(event, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert resp["statusCode"] == 500
    assert "Failed to generate upload URLs" in resp["body"]


def test_secrets_and_presigned_urls_not_logged(default_env, mock_dynamodb, mock_s3, caplog):
    caplog.set_level(logging.DEBUG)
    event = {"body": json.dumps({"files": [{"filename": "doc.pdf", "fileSizeBytes": 2_000_000}]})}

    response = handler(event, dynamodb_client=mock_dynamodb, s3_client=mock_s3)
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    secret = body["secret"]
    upload_url = body["uploads"][0]["uploadUrl"]

    for record in caplog.records:
        assert secret not in record.message
        assert upload_url not in record.message


def test_default_client_factories(monkeypatch):
    with patch("boto3.client") as mock_boto:
        from submit.lambda_handler import get_dynamodb_client, get_s3_client

        get_dynamodb_client()
        mock_boto.assert_called_with("dynamodb")

        get_s3_client()
        mock_boto.assert_called_with("s3")


def test_invalid_int_env_vars_fallback(monkeypatch):
    monkeypatch.setenv("TICKETS_TABLE_NAME", "pii-tickets-test")
    monkeypatch.setenv("UPLOADS_BUCKET_NAME", "pii-uploads-test")
    monkeypatch.setenv("MAX_FILES", "not-an-int")
    monkeypatch.setenv("MAX_TOTAL_BYTES", "not-an-int")
    monkeypatch.setenv("PRESIGNED_EXPIRY_SECONDS", "not-an-int")
    monkeypatch.setenv("TICKET_TTL_SECONDS", "not-an-int")

    with (
        patch("submit.lambda_handler.get_dynamodb_client") as mock_d,
        patch("submit.lambda_handler.get_s3_client") as mock_s,
    ):
        d_inst = MagicMock()
        d_inst.put_item.return_value = {}
        d_inst.update_item.return_value = {}
        mock_d.return_value = d_inst

        s_inst = MagicMock()
        s_inst.generate_presigned_url.return_value = "https://s3.amazonaws.com/test"
        mock_s.return_value = s_inst

        event = {
            "body": json.dumps(
                {"files": [{"filename": "statement.pdf", "fileSizeBytes": 2_000_000}]}
            )
        }
        resp = handler(event)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["expiresInSeconds"] == 900
