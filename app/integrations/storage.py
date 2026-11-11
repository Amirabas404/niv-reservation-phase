"""Private file storage for receipts, monthly exports and database backups.

Nothing here is ever served publicly. Access goes through the Backend, which checks permissions.
Two providers share one interface:
  - local: a private folder (development, tests)
  - r2:    Cloudflare R2 through its S3-compatible API (production on Railway)
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

ALLOWED_RECEIPT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_RECEIPT_BYTES = 10 * 1024 * 1024


class PrivateStorage(Protocol):
    async def save(self, data: bytes, content_type: str) -> str: ...
    async def save_named(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...
    async def read(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def list_keys(self, prefix: str) -> list[str]: ...


def new_receipt_key(content_type: str) -> str:
    ext = ALLOWED_RECEIPT_TYPES[content_type]
    return f"receipts/{datetime.now(UTC):%Y/%m}/{uuid4().hex}.{ext}"


class LocalPrivateStorage:
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()

    def _path(self, key: str) -> Path:
        path = (self._base / key).resolve()
        if self._base not in path.parents:
            raise ValueError("invalid storage key")
        return path

    async def save(self, data: bytes, content_type: str) -> str:
        key = new_receipt_key(content_type)
        await asyncio.to_thread(self._write, self._path(key), data)
        return key

    async def save_named(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        await asyncio.to_thread(self._write, self._path(key), data)
        return key

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(lambda: self._path(key).unlink(missing_ok=True))

    async def list_keys(self, prefix: str) -> list[str]:
        def _list() -> list[str]:
            root = self._base / prefix
            if not root.exists():
                return []
            return sorted(str(p.relative_to(self._base)) for p in root.rglob("*") if p.is_file())
        return await asyncio.to_thread(_list)

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class R2Storage:
    """Cloudflare R2 (S3-compatible). Bucket must be PRIVATE; no public access or custom domain."""

    def __init__(self, endpoint_url: str, bucket: str, access_key: str, secret_key: str) -> None:
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

    async def save(self, data: bytes, content_type: str) -> str:
        key = new_receipt_key(content_type)
        await asyncio.to_thread(self._put, key, data, content_type)
        return key

    async def save_named(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        await asyncio.to_thread(self._put, key, data, content_type)
        return key

    async def read(self, key: str) -> bytes:
        def _get() -> bytes:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        return await asyncio.to_thread(_get)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(lambda: self._client.delete_object(Bucket=self._bucket, Key=key))

    async def list_keys(self, prefix: str) -> list[str]:
        def _list() -> list[str]:
            keys: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                keys.extend(obj["Key"] for obj in page.get("Contents", []))
            return sorted(keys)
        return await asyncio.to_thread(_list)

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)


def get_storage() -> PrivateStorage:
    from app.core.config import get_settings

    s = get_settings()
    if s.storage_provider == "r2":
        missing = [name for name, v in (("STORAGE_ENDPOINT_URL", s.storage_endpoint_url),
                                        ("STORAGE_BUCKET", s.storage_bucket),
                                        ("STORAGE_ACCESS_KEY", s.storage_access_key),
                                        ("STORAGE_SECRET_KEY", s.storage_secret_key)) if not v]
        if missing:
            raise RuntimeError(f"R2 storage selected but missing: {', '.join(missing)}")
        return R2Storage(s.storage_endpoint_url, s.storage_bucket,
                         s.storage_access_key.get_secret_value(), s.storage_secret_key.get_secret_value())
    return LocalPrivateStorage(s.private_storage_dir)
