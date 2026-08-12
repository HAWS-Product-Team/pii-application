import boto3
import pandas as pd
import io
import os
from urllib.parse import urlparse
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

def is_s3_uri(path):
    """Check if the path is an S3 URI."""
    return path.startswith("s3://")

def parse_s3_uri(uri):
    """Parse S3 URI into bucket and key."""
    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket:
        raise ValueError(f"Invalid S3 URI (missing bucket): {uri}")
    if not key:
        raise ValueError(f"Invalid S3 URI (missing key): {uri}")
    return bucket, key

def read_input(path):
    """Read input from either local file or S3 URI."""
    if is_s3_uri(path):
        bucket, key = parse_s3_uri(path)
        try:
            s3 = boto3.client("s3")
            response = s3.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read()
            # Decode using same behavior as local file (pandas default)
            return pd.read_csv(io.BytesIO(content))
        except NoCredentialsError:
            raise RuntimeError("AWS credentials not found.")
        except PartialCredentialsError:
            raise RuntimeError("Incomplete AWS credentials.")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchBucket":
                raise RuntimeError(f"S3 bucket does not exist: {bucket}")
            elif error_code == "NoSuchKey":
                raise RuntimeError(f"S3 object does not exist: {key}")
            elif error_code in ["403", "AccessDenied"]:
                raise RuntimeError(f"Access denied to S3 object: {path}")
            else:
                raise RuntimeError(f"Failed to read S3 object: {e}")
        except Exception as e:
            raise RuntimeError(f"Error reading S3 object: {e}")
    else:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Local file does not exist: {path}")
        return pd.read_csv(path)

def write_output(df, path):
    """Write output to either local file or S3 URI."""
    if is_s3_uri(path):
        bucket, key = parse_s3_uri(path)
        try:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            s3 = boto3.client("s3")
            s3.put_object(Bucket=bucket, Key=key, Body=csv_buffer.getvalue())
        except NoCredentialsError:
            raise RuntimeError("AWS credentials not found.")
        except PartialCredentialsError:
            raise RuntimeError("Incomplete AWS credentials.")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchBucket":
                raise RuntimeError(f"S3 bucket does not exist: {bucket}")
            elif error_code in ["403", "AccessDenied"]:
                raise RuntimeError(f"Access denied to S3 object: {path}")
            else:
                raise RuntimeError(f"Failed to write S3 object: {e}")
        except Exception as e:
            raise RuntimeError(f"Error writing S3 object: {e}")
    else:
        df.to_csv(path, index=False)
