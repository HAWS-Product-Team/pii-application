"""Unit tests for the Normalizer Lambda handler."""

import io
import logging
import os
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from pdf2csv.lambda_handler import (
    DEFAULT_EPHEMERAL_STORAGE_BUDGET,
    Pdf2CsvError,
    Pdf2csvError,
    get_s3_client,
    handler,
)


class MockPaginator:
    """Mock boto3 S3 paginator."""

    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **kwargs):
        yield from self.pages


def create_fake_s3_client(objects_dict=None):
    """Create a mock S3 client with simulated object store."""
    client = MagicMock()
    store = objects_dict or {}

    def list_objects_v2(Bucket, Prefix="", **kwargs):
        matching = []
        for key, (content, size) in store.items():
            if key.startswith(Prefix):
                matching.append({"Key": key, "Size": size})
        return {"Contents": matching}

    def get_paginator(operation_name):
        if operation_name == "list_objects_v2":
            return MockPaginator([list_objects_v2(Bucket="mock", Prefix="")])
        raise NotImplementedError

    def download_file(Bucket, Key, Filename, **kwargs):
        if Key not in store:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject")
        content, _ = store[Key]
        with open(Filename, "wb") as f:
            f.write(content)

    def get_object(Bucket, Key, **kwargs):
        if Key not in store:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject")
        content, _ = store[Key]
        return {"Body": io.BytesIO(content)}

    uploaded_objects = {}

    def put_object(Bucket, Key, Body, ContentType="text/csv", **kwargs):
        uploaded_objects[Key] = (Body, ContentType)
        return {"ETag": "mock-etag"}

    client.list_objects_v2.side_effect = list_objects_v2
    client.get_paginator.side_effect = get_paginator
    client.download_file.side_effect = download_file
    client.get_object.side_effect = get_object
    client.put_object.side_effect = put_object
    client.uploaded_objects = uploaded_objects

    return client


def fake_conversion(input_path, output_path=None, **kwargs):
    """Simulate successful conversion producing a CSV for every PDF in input_dir."""
    for f in os.listdir(input_path):
        if f.lower().endswith(".pdf"):
            base = f[:-4]
            csv_path = os.path.join(output_path, f"{base}.csv")
            with open(csv_path, "w", encoding="utf-8") as out:
                out.write("date,item_description,quantity,unit_price,total_price\n")
                out.write("2024-01-01,Test Item,1,10.00,10.00\n")
    return 0


# Case 1: Valid event -> success response
def test_valid_event_success(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=fake_conversion)

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/statement.pdf": (b"%PDF-1.4 mock content", 100),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    response = handler(event, s3_client=fake_s3)

    assert response == {
        "ticket": "123456789",
        "status": "SUCCEEDED",
        "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload",
    }
    assert "123456789/upload/statement.csv" in fake_s3.uploaded_objects


# Case 2: Missing input-s3-uri -> Pdf2CsvError
@pytest.mark.parametrize(
    "invalid_event",
    [
        {},
        {"other_key": "s3://bucket/123/upload"},
        {"input-s3-uri": ""},
        {"input-s3-uri": None},
        "not-a-dict",
    ],
)
def test_event_missing_or_invalid_input_s3_uri(invalid_event):
    with pytest.raises(Pdf2CsvError):
        handler(invalid_event)


# Case 3: Malformed S3 URIs -> Pdf2CsvError
@pytest.mark.parametrize(
    "uri",
    [
        "http://pii-data-pipeline-input-dev/123456789/upload",
        "https://example.com/123456789/upload",
        "s3://",
        "s3://bucket",
        "s3:///123456789/upload",
        "ftp://bucket/123456789/upload",
    ],
)
def test_malformed_s3_uri(uri):
    with pytest.raises(Pdf2CsvError):
        handler({"input-s3-uri": uri})


# Case 4: Missing or invalid (non-numeric) ticket -> Pdf2CsvError
@pytest.mark.parametrize(
    "uri",
    [
        "s3://bucket/",
        "s3://bucket/upload",
        "s3://bucket/ticket_123/upload",
        "s3://bucket/abc/123",
    ],
)
def test_missing_or_invalid_ticket(uri):
    with pytest.raises(Pdf2CsvError):
        handler({"input-s3-uri": uri})


# Case 5: Trailing-slash URI accepted and handled identically
def test_trailing_slash_uri_accepted(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=fake_conversion)

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/statement.pdf": (b"%PDF-1.4 mock content", 100),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload/"}
    response = handler(event, s3_client=fake_s3)

    assert response == {
        "ticket": "123456789",
        "status": "SUCCEEDED",
        "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload/",
    }
    assert "123456789/upload/statement.csv" in fake_s3.uploaded_objects


# Case 6: PDFs listed and downloaded, conversion invoked over directory
def test_pdfs_listed_downloaded_conversion_invoked(mocker):
    mock_convert = mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=fake_conversion)

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/file1.pdf": (b"%PDF-1.4 file 1", 100),
            "123456789/upload/file2.pdf": (b"%PDF-1.4 file 2", 200),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    response = handler(event, s3_client=fake_s3)

    assert response["status"] == "SUCCEEDED"
    assert mock_convert.call_count == 1
    call_args = mock_convert.call_args[1]
    assert "input_path" in call_args and "output_path" in call_args


# Case 7: CSVs uploaded to correct keys (.csv extension)
def test_csvs_uploaded_to_correct_keys(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=fake_conversion)

    fake_s3 = create_fake_s3_client(
        {
            "99999/upload/order1.pdf": (b"%PDF-1.4 order 1", 50),
            "99999/upload/order2.PDF": (b"%PDF-1.4 order 2", 60),
        }
    )

    event = {"input-s3-uri": "s3://my-bucket/99999/upload"}
    handler(event, s3_client=fake_s3)

    assert "99999/upload/order1.csv" in fake_s3.uploaded_objects
    assert "99999/upload/order2.csv" in fake_s3.uploaded_objects


# Case 8: No PDFs at input prefix -> Pdf2CsvError
def test_no_pdfs_at_prefix():
    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/notes.txt": (b"plain text", 50),
            "123456789/upload/data.csv": (b"csv data", 50),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3)
    assert "no PDFs" in str(exc_info.value)
    assert "123456789" in str(exc_info.value)


# Case 9: Total input size exceeds budget -> Pdf2CsvError before download
def test_total_input_size_exceeds_budget(mocker):
    mock_convert = mocker.patch("pdf2csv.lambda_handler.process_input")

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/large1.pdf": (b"large", 3 * 1024 * 1024 * 1024),
            "123456789/upload/large2.pdf": (b"large", 2 * 1024 * 1024 * 1024),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3, storage_budget=DEFAULT_EPHEMERAL_STORAGE_BUDGET)

    assert "ephemeral storage budget" in str(exc_info.value)
    assert "123456789" in str(exc_info.value)
    # Ensure download and conversion were not attempted
    assert fake_s3.download_file.call_count == 0
    assert mock_convert.call_count == 0


# Case 10: S3 read failure -> Pdf2CsvError
def test_s3_read_failure_listing():
    fake_s3 = MagicMock()
    fake_s3.get_paginator.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
        "ListObjectsV2",
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3)
    assert "S3 read failure" in str(exc_info.value)
    assert "123456789" in str(exc_info.value)


def test_s3_read_failure_downloading(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input")
    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/test.pdf": (b"%PDF-1.4 content", 100),
        }
    )
    fake_s3.download_file.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
        "GetObject",
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3)
    assert "S3 read failure" in str(exc_info.value)
    assert "123456789/upload/test.pdf" in str(exc_info.value)


# Case 11: S3 write failure -> Pdf2CsvError
def test_s3_write_failure(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=fake_conversion)
    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/test.pdf": (b"%PDF-1.4 content", 100),
        }
    )
    fake_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
        "PutObject",
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3)
    assert "S3 write failure" in str(exc_info.value)
    assert "123456789/upload/test.csv" in str(exc_info.value)


# Case 12: Conversion produces no CSV -> Pdf2CsvError
def test_conversion_produces_no_csv(mocker):
    # Process_input runs but outputs nothing
    mocker.patch("pdf2csv.lambda_handler.process_input", return_value=0)

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/bad.pdf": (b"%PDF-1.4 corrupted", 100),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3)
    assert "conversion produced no CSV" in str(exc_info.value)
    assert "123456789/upload/bad.pdf" in str(exc_info.value)


def test_conversion_failure_exit_code(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input", return_value=1)

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/bad.pdf": (b"%PDF-1.4 corrupted", 100),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3)
    assert "conversion failed" in str(exc_info.value)


# Case 13: No PDF/CSV contents in logs or stdout
def test_no_pdf_or_csv_contents_in_logs_or_stdout(mocker, capsys, caplog):
    secret_string = "CONFIDENTIAL_PII_SSN_987654321"

    def secret_conversion(input_path, output_path=None, **kwargs):
        for f in os.listdir(input_path):
            if f.lower().endswith(".pdf"):
                base = f[:-4]
                csv_path = os.path.join(output_path, f"{base}.csv")
                with open(csv_path, "w", encoding="utf-8") as out:
                    out.write(
                        f"date,item_description,quantity,unit_price,total_price\n2024-01-01,{secret_string},1,10.00,10.00\n"
                    )
        return 0

    mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=secret_conversion)

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/statement.pdf": (f"%PDF-1.4 {secret_string}".encode(), 100),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with caplog.at_level(logging.DEBUG):
        response = handler(event, s3_client=fake_s3)

    assert response["status"] == "SUCCEEDED"

    captured = capsys.readouterr()
    assert secret_string not in captured.out
    assert secret_string not in captured.err
    assert secret_string not in caplog.text


def test_get_s3_client_factory(mocker):
    mock_boto = mocker.patch("boto3.client")
    client = get_s3_client()
    mock_boto.assert_called_once_with("s3")
    assert client == mock_boto.return_value

    custom_client = MagicMock()
    assert get_s3_client(custom_client) == custom_client


def test_alias_compatibility():
    assert Pdf2csvError is Pdf2CsvError


def test_fallback_s3_methods(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=fake_conversion)

    # Client without get_paginator, without download_file, without put_object
    client = MagicMock(spec=["list_objects_v2", "get_object", "upload_file"])
    client.list_objects_v2.return_value = {
        "Contents": [{"Key": "123456789/upload/stmt.pdf", "Size": 100}]
    }
    client.get_object.return_value = {"Body": io.BytesIO(b"%PDF-1.4 mock")}

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    response = handler(event, s3_client=client)

    assert response["status"] == "SUCCEEDED"
    assert client.upload_file.call_count == 1


def test_duplicate_basenames_handling(mocker):
    mocker.patch("pdf2csv.lambda_handler.process_input", side_effect=fake_conversion)

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/dir1/statement.pdf": (b"%PDF-1.4 mock 1", 100),
            "123456789/upload/dir2/statement.pdf": (b"%PDF-1.4 mock 2", 100),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    response = handler(event, s3_client=fake_s3)

    assert response["status"] == "SUCCEEDED"
    assert "123456789/upload/dir1/statement.csv" in fake_s3.uploaded_objects
    assert "123456789/upload/dir2/statement.csv" in fake_s3.uploaded_objects


def test_conversion_exception_handling(mocker):
    mocker.patch(
        "pdf2csv.lambda_handler.process_input", side_effect=RuntimeError("Converter crashed")
    )

    fake_s3 = create_fake_s3_client(
        {
            "123456789/upload/statement.pdf": (b"%PDF-1.4 mock", 100),
        }
    )

    event = {"input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload"}
    with pytest.raises(Pdf2CsvError) as exc_info:
        handler(event, s3_client=fake_s3)
    assert "conversion failed" in str(exc_info.value)
