"""Storage adapters for the CSV merge step.

The merge logic depends only on the small ``Storage`` protocol defined here, so
the same core function runs against the local filesystem (development, unit
tests) or S3 (Lambda) without changing.
"""

from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, TextIO
from urllib.parse import urlparse

# csv module requires newline="" so it can handle quoted fields that contain
# newlines. utf-8-sig strips a BOM if the upstream PDF-to-CSV step emits one.
_READ_ENCODING = "utf-8-sig"
_WRITE_ENCODING = "utf-8"


class Storage(Protocol):
    """Everything the merge core needs from the outside world."""

    def list_csvs(self, location: str) -> list[str]:
        """Return CSV paths under ``location``, in a stable sorted order."""

    def basename(self, path: str) -> str:
        """Return the filename portion of ``path``."""

    @contextmanager
    def open_read(self, path: str) -> Iterator[TextIO]:
        """Open ``path`` for streaming text reads."""

    @contextmanager
    def open_write(self, path: str) -> Iterator[TextIO]:
        """Open ``path`` for streaming text writes."""


class LocalStorage:
    """Reads and writes on the local filesystem."""

    def list_csvs(self, location: str) -> list[str]:
        directory = Path(location)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {location}")
        return sorted(str(p) for p in directory.glob("*.csv") if p.is_file())

    def basename(self, path: str) -> str:
        return os.path.basename(path)

    @contextmanager
    def open_read(self, path: str) -> Iterator[TextIO]:
        with open(path, "r", newline="", encoding=_READ_ENCODING) as handle:
            yield handle

    @contextmanager
    def open_write(self, path: str) -> Iterator[TextIO]:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", newline="", encoding=_WRITE_ENCODING) as handle:
            yield handle


class S3Storage:
    """Reads and writes s3:// URIs.

    Reads stream straight off the response body. Writes are staged in /tmp and
    uploaded on close, so memory stays flat regardless of output size.
    """

    def __init__(self, client=None, tmp_dir: str = "/tmp"):
        if client is None:
            import boto3  # imported lazily so local runs don't need boto3

            client = boto3.client("s3")
        self._client = client
        self._tmp_dir = tmp_dir

    @staticmethod
    def parse_uri(uri: str) -> tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != "s3":
            raise ValueError(f"Not an s3:// URI: {uri}")
        return parsed.netloc, parsed.path.lstrip("/")

    def list_csvs(self, location: str) -> list[str]:
        bucket, prefix = self.parse_uri(location)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".csv"):
                    keys.append(f"s3://{bucket}/{key}")
        return sorted(keys)

    def basename(self, path: str) -> str:
        return path.rsplit("/", 1)[-1]

    @contextmanager
    def open_read(self, path: str) -> Iterator[TextIO]:
        bucket, key = self.parse_uri(path)
        body = self._client.get_object(Bucket=bucket, Key=key)["Body"]
        wrapper = io.TextIOWrapper(body, encoding=_READ_ENCODING, newline="")
        try:
            yield wrapper
        finally:
            wrapper.close()

    @contextmanager
    def open_write(self, path: str) -> Iterator[TextIO]:
        bucket, key = self.parse_uri(path)
        fd, staged = tempfile.mkstemp(suffix=".csv", dir=self._tmp_dir)
        os.close(fd)
        try:
            with open(staged, "w", newline="", encoding=_WRITE_ENCODING) as handle:
                yield handle
            self._client.upload_file(staged, bucket, key)
        finally:
            if os.path.exists(staged):
                os.remove(staged)


class AutoStorage:
    """Dispatches each path to local or S3 based on its scheme.

    Lets a run read from a local directory and write to S3, or vice versa,
    without the core knowing anything about either.
    """

    def __init__(self, local: Storage = None, s3: Storage = None):
        self._local = local or LocalStorage()
        self._s3 = s3
        self._s3_factory = S3Storage

    def _for(self, path: str) -> Storage:
        if path.startswith("s3://"):
            if self._s3 is None:
                self._s3 = self._s3_factory()
            return self._s3
        return self._local

    def list_csvs(self, location: str) -> list[str]:
        return self._for(location).list_csvs(location)

    def basename(self, path: str) -> str:
        return self._for(path).basename(path)

    @contextmanager
    def open_read(self, path: str) -> Iterator[TextIO]:
        with self._for(path).open_read(path) as handle:
            yield handle

    @contextmanager
    def open_write(self, path: str) -> Iterator[TextIO]:
        with self._for(path).open_write(path) as handle:
            yield handle
