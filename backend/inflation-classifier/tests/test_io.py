import pytest
import pandas as pd
import io
from unittest.mock import Mock
from botocore.exceptions import ClientError, NoCredentialsError
from inflation_classifier.io import is_s3_uri, parse_s3_uri, read_input, write_output

def test_is_s3_uri():
    assert is_s3_uri("s3://bucket/key") is True
    assert is_s3_uri("s3://bucket") is True
    assert is_s3_uri("/local/path") is False
    assert is_s3_uri("http://example.com") is False

def test_parse_s3_uri():
    assert parse_s3_uri("s3://my-bucket/path/to/file.csv") == ("my-bucket", "path/to/file.csv")
    assert parse_s3_uri("s3://another-bucket/file.csv") == ("another-bucket", "file.csv")
    
    with pytest.raises(ValueError, match="Invalid S3 URI"):
        parse_s3_uri("not-s3://bucket/key")
    
    with pytest.raises(ValueError, match="missing bucket"):
        parse_s3_uri("s3:///key")
    
    with pytest.raises(ValueError, match="missing key"):
        parse_s3_uri("s3://bucket")
    
    with pytest.raises(ValueError, match="missing key"):
        parse_s3_uri("s3://bucket/")

def test_read_input_s3_success(mocker):
    mocked_s3 = Mock()
    mocked_s3.get_object.return_value = {
        "Body": io.BytesIO(
            b"item_description,category,difficulty\nitem1,cat1,easy\nitem2,cat2,hard"
        )
    }
    mocker.patch("inflation_classifier.io.boto3.client", return_value=mocked_s3)

    df = read_input("s3://test-bucket/data.csv")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.iloc[0]["item_description"] == "item1"

def test_read_input_s3_bucket_not_found(mocker):
    mocked_s3 = Mock()
    mocked_s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"}},
        "GetObject",
    )
    mocker.patch("inflation_classifier.io.boto3.client", return_value=mocked_s3)

    with pytest.raises(RuntimeError, match="S3 bucket does not exist: non-existent-bucket"):
        read_input("s3://non-existent-bucket/file.csv")

def test_read_input_s3_object_not_found(mocker):
    mocked_s3 = Mock()
    mocked_s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist"}},
        "GetObject",
    )
    mocker.patch("inflation_classifier.io.boto3.client", return_value=mocked_s3)

    with pytest.raises(RuntimeError, match="S3 object does not exist: missing.csv"):
        read_input("s3://test-bucket/missing.csv")


def test_read_input_s3_malformed_uri():
    with pytest.raises(ValueError, match="missing bucket"):
        read_input("s3://")


def test_read_input_s3_credentials_missing(mocker):
    mocked_s3 = Mock()
    mocked_s3.get_object.side_effect = NoCredentialsError()
    mocker.patch("inflation_classifier.io.boto3.client", return_value=mocked_s3)

    with pytest.raises(RuntimeError, match="AWS credentials not found"):
        read_input("s3://test-bucket/file.csv")

def test_read_input_local_success(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    f = d / "test.csv"
    content = "item_description,category,difficulty\nitem1,cat1,easy"
    f.write_text(content)
    
    df = read_input(str(f))
    assert len(df) == 1
    assert df.iloc[0]["item_description"] == "item1"

def test_read_input_local_not_found():
    with pytest.raises(FileNotFoundError):
        read_input("non_existent_file.csv")

def test_write_output_local_success(tmp_path):
    f = tmp_path / "output.csv"
    df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    write_output(df, str(f))
    
    assert f.exists()
    loaded_df = pd.read_csv(f)
    pd.testing.assert_frame_equal(df, loaded_df)

def test_write_output_s3_success(mocker):
    mocked_s3 = Mock()
    mocker.patch("inflation_classifier.io.boto3.client", return_value=mocked_s3)
    
    df = pd.DataFrame({"col1": [1]})
    write_output(df, "s3://test-bucket/output.csv")
    
    mocked_s3.put_object.assert_called_once()
    args, kwargs = mocked_s3.put_object.call_args
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == "output.csv"
    assert "col1" in kwargs["Body"]
