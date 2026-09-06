"""Unit tests for the storage layer (LocalStorage, S3Storage, and AutoStorage)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from merge.storage import AutoStorage, LocalStorage, S3Storage


def test_local_storage_list_csvs_and_basename(tmp_path):
    storage = LocalStorage()
    (tmp_path / "b.csv").write_text("b")
    (tmp_path / "a.csv").write_text("a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.csv").write_text("c")
    (tmp_path / "notes.txt").write_text("txt")

    csvs = storage.list_csvs(str(tmp_path))
    assert [storage.basename(p) for p in csvs] == ["a.csv", "b.csv"]


def test_local_storage_list_csvs_not_a_directory(tmp_path):
    storage = LocalStorage()
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")

    with pytest.raises(NotADirectoryError):
        storage.list_csvs(str(file_path))


def test_local_storage_open_read_write(tmp_path):
    storage = LocalStorage()
    target = tmp_path / "nested" / "dir" / "out.csv"

    with storage.open_write(str(target)) as handle:
        handle.write("col1,col2\nval1,val2\n")

    assert target.exists()

    with storage.open_read(str(target)) as handle:
        content = handle.read()

    assert content == "col1,col2\nval1,val2\n"


def test_s3_storage_parse_uri():
    bucket, key = S3Storage.parse_uri("s3://my-bucket/path/to/data.csv")
    assert bucket == "my-bucket"
    assert key == "path/to/data.csv"

    with pytest.raises(ValueError, match="Not an s3:// URI"):
        S3Storage.parse_uri("https://my-bucket/path/to/data.csv")


def test_s3_storage_init_lazy_boto3():
    mock_boto = MagicMock()
    mock_client = MagicMock()
    mock_boto.client.return_value = mock_client
    with patch.dict("sys.modules", {"boto3": mock_boto}):
        storage = S3Storage()
        assert storage._client is mock_client
        mock_boto.client.assert_called_once_with("s3")


def test_s3_storage_list_csvs():
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_client.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {"Key": "input/b.csv"},
                {"Key": "input/notes.txt"},
                {"Key": "input/a.csv"},
            ]
        },
        {
            "Contents": [
                {"Key": "input/c.CSV"},
            ]
        },
    ]

    storage = S3Storage(client=mock_client)
    # Test with prefix without trailing slash
    results = storage.list_csvs("s3://test-bucket/input")

    mock_client.get_paginator.assert_called_once_with("list_objects_v2")
    mock_paginator.paginate.assert_called_once_with(
        Bucket="test-bucket", Prefix="input/"
    )
    assert results == [
        "s3://test-bucket/input/a.csv",
        "s3://test-bucket/input/b.csv",
        "s3://test-bucket/input/c.CSV",
    ]


def test_s3_storage_basename():
    storage = S3Storage(client=MagicMock())
    assert storage.basename("s3://bucket/dir/sub/file.csv") == "file.csv"


def test_s3_storage_open_read():
    mock_client = MagicMock()
    fake_body = io.BytesIO(b"col1,col2\n1,2\n")
    mock_client.get_object.return_value = {"Body": fake_body}

    storage = S3Storage(client=mock_client)
    with storage.open_read("s3://test-bucket/input/data.csv") as handle:
        data = handle.read()

    mock_client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="input/data.csv"
    )
    assert data == "col1,col2\n1,2\n"


def test_s3_storage_open_write(tmp_path):
    mock_client = MagicMock()
    storage = S3Storage(client=mock_client, tmp_dir=str(tmp_path))

    with storage.open_write("s3://test-bucket/out/merged.csv") as handle:
        handle.write("header1,header2\n")

    mock_client.upload_file.assert_called_once()
    args, _ = mock_client.upload_file.call_args
    staged_path, bucket, key = args
    assert bucket == "test-bucket"
    assert key == "out/merged.csv"
    # Verify staged file was cleaned up
    assert not Path(staged_path).exists()


def test_s3_storage_open_write_cleanup_on_error(tmp_path):
    mock_client = MagicMock()
    mock_client.upload_file.side_effect = RuntimeError("S3 upload failed")
    storage = S3Storage(client=mock_client, tmp_dir=str(tmp_path))

    with (
        pytest.raises(RuntimeError, match="S3 upload failed"),
        storage.open_write("s3://test-bucket/out/merged.csv") as handle,
    ):
        handle.write("header1,header2\n")

    # Verify no leaked files in tmp_path
    assert list(tmp_path.glob("*.csv")) == []


def test_auto_storage_delegation():
    mock_local = MagicMock(spec=LocalStorage)
    mock_s3 = MagicMock(spec=S3Storage)

    storage = AutoStorage(local=mock_local, s3=mock_s3)

    # Local dispatch
    storage.list_csvs("local/dir")
    mock_local.list_csvs.assert_called_once_with("local/dir")

    storage.basename("local/dir/a.csv")
    mock_local.basename.assert_called_once_with("local/dir/a.csv")

    with storage.open_read("local/dir/a.csv"):
        pass
    mock_local.open_read.assert_called_once_with("local/dir/a.csv")

    with storage.open_write("local/dir/a.csv"):
        pass
    mock_local.open_write.assert_called_once_with("local/dir/a.csv")

    # S3 dispatch
    storage.list_csvs("s3://bucket/dir")
    mock_s3.list_csvs.assert_called_once_with("s3://bucket/dir")

    storage.basename("s3://bucket/dir/a.csv")
    mock_s3.basename.assert_called_once_with("s3://bucket/dir/a.csv")

    with storage.open_read("s3://bucket/dir/a.csv"):
        pass
    mock_s3.open_read.assert_called_once_with("s3://bucket/dir/a.csv")

    with storage.open_write("s3://bucket/dir/a.csv"):
        pass
    mock_s3.open_write.assert_called_once_with("s3://bucket/dir/a.csv")


def test_auto_storage_lazy_s3_creation():
    storage = AutoStorage()
    assert storage._s3 is None

    with patch.object(storage, "_s3_factory") as mock_factory:
        mock_instance = MagicMock(spec=S3Storage)
        mock_factory.return_value = mock_instance

        storage.list_csvs("s3://bucket/prefix")
        mock_factory.assert_called_once()
        assert storage._s3 is mock_instance
