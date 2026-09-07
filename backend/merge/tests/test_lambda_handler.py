"""Unit tests for the Merge Lambda handler (merge.lambda_handler)."""

from __future__ import annotations

import csv
import logging
from unittest.mock import MagicMock

import pytest

from merge.lambda_handler import DEFAULT_MAX_INPUT_BYTES, handler
from merge.merger import MergeError


def _create_mock_s3(
    csv_contents: dict[str, str] | None = None,
    custom_contents: list[dict] | None = None,
    list_error: Exception | None = None,
    download_error: Exception | None = None,
    upload_error: Exception | None = None,
):
    """Create a mock boto3 S3 client for testing the lambda handler."""
    mock_client = MagicMock()

    # Configure listing
    if list_error:
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = list_error
        mock_client.get_paginator.return_value = mock_paginator
    elif custom_contents is not None:
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": custom_contents}]
        mock_client.get_paginator.return_value = mock_paginator
    elif csv_contents is not None:
        contents = [
            {"Key": key, "Size": len(content.encode("utf-8"))}
            for key, content in csv_contents.items()
        ]
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": contents}]
        mock_client.get_paginator.return_value = mock_paginator
    else:
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{}]
        mock_client.get_paginator.return_value = mock_paginator

    # Configure downloading
    def fake_download(bucket, key, local_path):
        if download_error:
            raise download_error
        if csv_contents and key in csv_contents:
            with open(local_path, "w", newline="", encoding="utf-8") as f:
                f.write(csv_contents[key])

    mock_client.download_file.side_effect = fake_download

    # Configure uploading
    uploaded_files: dict[tuple[str, str], str] = {}

    def fake_upload(local_path, bucket, key):
        if upload_error:
            raise upload_error
        with open(local_path, "r", newline="", encoding="utf-8") as f:
            uploaded_files[(bucket, key)] = f.read()

    mock_client.upload_file.side_effect = fake_upload
    mock_client.uploaded_files = uploaded_files

    return mock_client


SAMPLE_HEADER = "date,item_description,quantity,unit_price,total_price\n"
SAMPLE_CSV_1 = SAMPLE_HEADER + "2026-01-01,Widget A,1,10.00,10.00\n"
SAMPLE_CSV_2 = SAMPLE_HEADER + "2026-01-02,Widget B,2,5.00,10.00\n"


# 1. Valid event -> success response with correct ticket, status, output-s3-uri.
def test_valid_event_success():
    csv_data = {
        "123456789/upload/file1.csv": SAMPLE_CSV_1,
        "123456789/upload/file2.csv": SAMPLE_CSV_2,
    }
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    event = {
        "input-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/upload",
        "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/purchase_data.csv",
    }

    result = handler(event, context=None, s3_client=s3_mock)

    assert result == {
        "ticket": "123456789",
        "status": "SUCCEEDED",
        "output-s3-uri": "s3://pii-data-pipeline-input-dev/123456789/purchase_data.csv",
    }
    assert (
        "pii-data-pipeline-input-dev",
        "123456789/purchase_data.csv",
    ) in s3_mock.uploaded_files


# 2. Event missing input-s3-uri -> MergeError.
def test_event_missing_input_s3_uri():
    event = {
        "output-s3-uri": "s3://bucket/1234/purchase_data.csv",
    }
    with pytest.raises(MergeError, match="Missing required event field: 'input-s3-uri'"):
        handler(event, s3_client=MagicMock())


# 3. Event missing output-s3-uri -> MergeError.
def test_event_missing_output_s3_uri():
    event = {
        "input-s3-uri": "s3://bucket/1234/upload",
    }
    with pytest.raises(MergeError, match="Missing required event field: 'output-s3-uri'"):
        handler(event, s3_client=MagicMock())


# 4. Malformed S3 URIs (http://..., s3://, s3://bucket) -> MergeError.
@pytest.mark.parametrize(
    "bad_input_uri",
    [
        "http://bucket/1234/upload",
        "https://bucket/1234/upload",
        "s3://",
        "s3://bucket",
        "s3://bucket/",
        "/local/path/1234/upload",
    ],
)
def test_malformed_input_s3_uri(bad_input_uri):
    event = {
        "input-s3-uri": bad_input_uri,
        "output-s3-uri": "s3://bucket/1234/purchase_data.csv",
    }
    with pytest.raises(MergeError):
        handler(event, s3_client=MagicMock())


@pytest.mark.parametrize(
    "bad_output_uri",
    [
        "http://bucket/1234/out.csv",
        "s3://",
        "s3://bucket",
        "s3://bucket/",
        "s3://bucket/1234/",
    ],
)
def test_malformed_output_s3_uri(bad_output_uri):
    event = {
        "input-s3-uri": "s3://bucket/1234/upload",
        "output-s3-uri": bad_output_uri,
    }
    with pytest.raises(MergeError):
        handler(event, s3_client=MagicMock())


# 5. Missing/invalid ticket (s3://bucket/, s3://bucket/upload, non-numeric) -> MergeError.
@pytest.mark.parametrize(
    "invalid_ticket_uri",
    [
        "s3://bucket/upload",
        "s3://bucket/abc-123/upload",
        "s3://bucket/ticket123/upload",
        "s3://bucket/-1234/upload",
    ],
)
def test_invalid_ticket_number(invalid_ticket_uri):
    event = {
        "input-s3-uri": invalid_ticket_uri,
        "output-s3-uri": "s3://bucket/purchase_data.csv",
    }
    with pytest.raises(MergeError, match="must be numeric"):
        handler(event, s3_client=MagicMock())


# 6. Trailing-slash URI accepted and handled identically.
def test_trailing_slash_uri_accepted():
    csv_data = {
        "998877/upload/item1.csv": SAMPLE_CSV_1,
    }
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    event = {
        "input-s3-uri": "s3://pii-bucket/998877/upload/",
        "output-s3-uri": "s3://pii-bucket/998877/purchase_data.csv",
    }

    result = handler(event, s3_client=s3_mock)
    assert result["ticket"] == "998877"
    assert result["status"] == "SUCCEEDED"
    assert result["output-s3-uri"] == "s3://pii-bucket/998877/purchase_data.csv"


# 7. CSVs are listed and downloaded from S3; conversion invoked over the directory.
def test_csvs_listed_and_downloaded():
    csv_data = {
        "12345/upload/a.csv": SAMPLE_CSV_1,
        "12345/upload/b.csv": SAMPLE_CSV_2,
    }
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    event = {
        "input-s3-uri": "s3://test-bucket/12345/upload",
        "output-s3-uri": "s3://test-bucket/12345/merged.csv",
    }

    handler(event, s3_client=s3_mock)

    assert s3_mock.download_file.call_count == 2
    uploaded = s3_mock.uploaded_files[("test-bucket", "12345/merged.csv")]
    reader = list(csv.reader(uploaded.splitlines()))
    assert reader[0] == ["date", "item_description", "quantity", "unit_price", "total_price"]
    assert len(reader) == 3  # Header + 2 rows


# 8. Output CSV uploaded to the correct key (output-s3-uri).
def test_output_csv_uploaded_to_correct_key():
    csv_data = {"456/in/a.csv": SAMPLE_CSV_1}
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    event = {
        "input-s3-uri": "s3://data-bucket/456/in",
        "output-s3-uri": "s3://target-bucket/456/final/purchase_data.csv",
    }

    handler(event, s3_client=s3_mock)

    assert ("target-bucket", "456/final/purchase_data.csv") in s3_mock.uploaded_files
    s3_mock.upload_file.assert_called_once()
    _local_path, bucket, key = s3_mock.upload_file.call_args[0]
    assert bucket == "target-bucket"
    assert key == "456/final/purchase_data.csv"


# 9. No CSVs at the prefix -> MergeError.
def test_no_csvs_at_prefix_raises_error():
    # Only non-CSV files in bucket
    custom_contents = [
        {"Key": "1234/upload/file.pdf", "Size": 1024},
        {"Key": "1234/upload/notes.txt", "Size": 512},
    ]
    s3_mock = _create_mock_s3(custom_contents=custom_contents)

    event = {
        "input-s3-uri": "s3://test-bucket/1234/upload",
        "output-s3-uri": "s3://test-bucket/1234/merged.csv",
    }

    with pytest.raises(MergeError, match="No CSVs found at input path"):
        handler(event, s3_client=s3_mock)


# 10. Total input size exceeds the /tmp budget -> MergeError (raised before any download).
def test_input_size_exceeds_budget_raised_before_download():
    custom_contents = [
        {"Key": "1234/upload/big1.csv", "Size": 3 * 1024 * 1024 * 1024},
        {"Key": "1234/upload/big2.csv", "Size": 2 * 1024 * 1024 * 1024},
    ]
    s3_mock = _create_mock_s3(custom_contents=custom_contents)

    event = {
        "input-s3-uri": "s3://test-bucket/1234/upload",
        "output-s3-uri": "s3://test-bucket/1234/merged.csv",
    }

    with pytest.raises(MergeError, match="exceeds ephemeral storage budget"):
        handler(event, s3_client=s3_mock, max_input_bytes=DEFAULT_MAX_INPUT_BYTES)

    # Verify no download was attempted
    s3_mock.download_file.assert_not_called()


# 11. S3 read failure -> MergeError.
def test_s3_read_failure_on_list():
    s3_mock = _create_mock_s3(list_error=RuntimeError("Access Denied"))

    event = {
        "input-s3-uri": "s3://test-bucket/1234/upload",
        "output-s3-uri": "s3://test-bucket/1234/merged.csv",
    }

    with pytest.raises(MergeError, match="S3 read failure"):
        handler(event, s3_client=s3_mock)


def test_s3_read_failure_on_download():
    csv_data = {"1234/upload/a.csv": SAMPLE_CSV_1}
    s3_mock = _create_mock_s3(
        csv_contents=csv_data, download_error=RuntimeError("S3 Connection Reset")
    )

    event = {
        "input-s3-uri": "s3://test-bucket/1234/upload",
        "output-s3-uri": "s3://test-bucket/1234/merged.csv",
    }

    with pytest.raises(MergeError, match="S3 read failure downloading"):
        handler(event, s3_client=s3_mock)


# 12. S3 write failure -> MergeError.
def test_s3_write_failure_on_upload():
    csv_data = {"1234/upload/a.csv": SAMPLE_CSV_1}
    s3_mock = _create_mock_s3(
        csv_contents=csv_data, upload_error=RuntimeError("S3 PutObject Access Denied")
    )

    event = {
        "input-s3-uri": "s3://test-bucket/1234/upload",
        "output-s3-uri": "s3://test-bucket/1234/merged.csv",
    }

    with pytest.raises(MergeError, match="S3 write failure uploading"):
        handler(event, s3_client=s3_mock)


# 13. Merge conversion failure (e.g., mismatched header) -> MergeError.
def test_conversion_failure_mismatched_headers():
    csv_data = {
        "1234/upload/a.csv": SAMPLE_HEADER + "2026-01-01,Widget A,1,10.00,10.00\n",
        "1234/upload/b.csv": "colA,colB,colC\n1,2,3\n",
    }
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    event = {
        "input-s3-uri": "s3://test-bucket/1234/upload",
        "output-s3-uri": "s3://test-bucket/1234/merged.csv",
    }

    with pytest.raises(MergeError, match="Conversion failure"):
        handler(event, s3_client=s3_mock)


# 14. No CSV contents appear in logs or stdout.
def test_no_csv_contents_in_logs_or_stdout(caplog, capsys):
    secret_marker = "CONFIDENTIAL_PII_DATA_12345"
    csv_with_secret = SAMPLE_HEADER + f"2026-01-01,{secret_marker},1,10.00,10.00\n"

    csv_data = {"12345/upload/a.csv": csv_with_secret}
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    event = {
        "input-s3-uri": "s3://test-bucket/12345/upload",
        "output-s3-uri": "s3://test-bucket/12345/merged.csv",
    }

    with caplog.at_level(logging.DEBUG):
        result = handler(event, s3_client=s3_mock)

    assert result["status"] == "SUCCEEDED"

    # Verify secret data is nowhere in captured logs or stdout/stderr
    captured_stdout = capsys.readouterr().out
    captured_stderr = capsys.readouterr().err
    assert secret_marker not in caplog.text
    assert secret_marker not in captured_stdout
    assert secret_marker not in captured_stderr


def test_event_not_dict():
    with pytest.raises(MergeError, match="Event must be a dictionary"):
        handler("not a dict", s3_client=MagicMock())


def test_get_s3_client_lazy_factory(monkeypatch):
    mock_boto = MagicMock()
    mock_client = MagicMock()
    mock_boto.client.return_value = mock_client
    monkeypatch.setattr("boto3.client", mock_boto.client)

    from merge.lambda_handler import get_s3_client

    client = get_s3_client()
    assert client is mock_client


def test_s3_client_default_creation(monkeypatch):
    csv_data = {"12345/upload/a.csv": SAMPLE_CSV_1}
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    monkeypatch.setattr("merge.lambda_handler.get_s3_client", lambda: s3_mock)

    event = {
        "input-s3-uri": "s3://test-bucket/12345/upload",
        "output-s3-uri": "s3://test-bucket/12345/merged.csv",
    }

    result = handler(event)
    assert result["status"] == "SUCCEEDED"


def test_s3_client_creation_failure(monkeypatch):
    def fail_factory():
        raise RuntimeError("AWS SDK init error")

    monkeypatch.setattr("merge.lambda_handler.get_s3_client", fail_factory)

    event = {
        "input-s3-uri": "s3://test-bucket/12345/upload",
        "output-s3-uri": "s3://test-bucket/12345/merged.csv",
    }

    with pytest.raises(MergeError, match="Failed to initialize S3 client"):
        handler(event)


def test_duplicate_filenames_nested_subfolders():
    csv_data = {
        "12345/upload/sub1/data.csv": SAMPLE_CSV_1,
        "12345/upload/sub2/data.csv": SAMPLE_CSV_2,
    }
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    event = {
        "input-s3-uri": "s3://test-bucket/12345/upload",
        "output-s3-uri": "s3://test-bucket/12345/merged.csv",
    }

    result = handler(event, s3_client=s3_mock)
    assert result["status"] == "SUCCEEDED"
    assert s3_mock.download_file.call_count == 2


def test_merge_produced_no_output_file(monkeypatch):
    csv_data = {"12345/upload/a.csv": SAMPLE_CSV_1}
    s3_mock = _create_mock_s3(csv_contents=csv_data)

    # Mock merge_csv_files to do nothing (not create output file)
    monkeypatch.setattr(
        "merge.lambda_handler.merge_csv_files",
        lambda **kwargs: MagicMock(file_count=1, total_rows=1),
    )

    event = {
        "input-s3-uri": "s3://test-bucket/12345/upload",
        "output-s3-uri": "s3://test-bucket/12345/merged.csv",
    }

    with pytest.raises(MergeError, match="Merge conversion produced no CSV output file"):
        handler(event, s3_client=s3_mock)
