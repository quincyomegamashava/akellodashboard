"""Pluggable object storage for submissions (local filesystem or S3-compatible)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import BinaryIO, Optional

from flask import Flask


class StorageBackend:
    def save_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> str:
        raise NotImplementedError

    def public_url(self, key: str) -> str:
        raise NotImplementedError


class LocalLearnStorage(StorageBackend):
    """Stores under Flask instance_path/learn_uploads/."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        return key

    def public_url(self, key: str) -> str:
        return f"/learn/uploads/{key}"


class S3LearnStorage(StorageBackend):
    """boto3 S3-compatible (AWS S3, MinIO, R2)."""

    def __init__(self, bucket: str, endpoint_url: Optional[str], region: str):
        import boto3  # lazy

        self.bucket = bucket
        kwargs = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self.client = boto3.client("s3", **kwargs)

    def save_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> str:
        extra = {}
        if length is not None:
            extra["ContentLength"] = length
        self.client.upload_fileobj(stream, self.bucket, key)
        return key

    def public_url(self, key: str) -> str:
        # Caller may prefer CloudFront/R2 public URL via env later
        return f"s3://{self.bucket}/{key}"


_storage: Optional[StorageBackend] = None


def get_storage(app: Flask) -> StorageBackend:
    global _storage
    if _storage is not None:
        return _storage

    bucket = app.config.get("LEARN_S3_BUCKET")
    key = app.config.get("AWS_ACCESS_KEY_ID")
    secret = app.config.get("AWS_SECRET_ACCESS_KEY")

    if bucket and key and secret:
        _storage = S3LearnStorage(
            bucket=bucket,
            endpoint_url=app.config.get("AWS_ENDPOINT_URL"),
            region=app.config.get("AWS_REGION", "us-east-1"),
        )
        return _storage

    root = Path(app.instance_path) / "learn_uploads"
    _storage = LocalLearnStorage(root)
    return _storage


def new_upload_key(prefix: str, original_name: str) -> str:
    ext = Path(original_name).suffix[:12] if original_name else ""
    return f"{prefix}/{uuid.uuid4().hex}{ext}"
