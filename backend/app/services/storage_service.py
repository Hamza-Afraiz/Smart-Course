"""Object-storage access (MinIO in dev, R2/S3 in prod) via the S3 API.

Two boto3 clients on purpose — this is the key MinIO-in-Docker subtlety:

  - PUBLIC client  (endpoint = localhost:9000) signs URLs the BROWSER uses.
    A presigned URL embeds the host it was signed for, so it must be signed
    against the host-reachable endpoint.
  - INTERNAL client (endpoint = minio:9000) is used by api/worker processes
    INSIDE the compose network for direct get_object — no presigning, so no
    host-mismatch problem.

Swapping MinIO → Cloudflare R2 / AWS S3 in production is purely env vars:
set both endpoints to the cloud endpoint and supply real credentials.
"""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache

import boto3
from botocore.client import Config

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _public_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_public_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


@lru_cache(maxsize=1)
def _internal_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_internal_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    """Create the bucket if it doesn't exist. Idempotent; call at startup."""
    c = _internal_client()
    existing = {b["Name"] for b in c.list_buckets().get("Buckets", [])}
    if settings.s3_bucket not in existing:
        c.create_bucket(Bucket=settings.s3_bucket)
        logger.info("created object-storage bucket: %s", settings.s3_bucket)


def make_key(filename: str, prefix: str = "lessons") -> str:
    """A collision-free storage key that preserves the original extension."""
    safe = filename.rsplit("/", 1)[-1].replace(" ", "_")
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else "bin"
    return f"{prefix}/{uuid.uuid4()}.{ext}"


def presign_put(key: str, content_type: str) -> str:
    """Browser PUTs the file bytes directly to this URL (bypasses our API)."""
    return _public_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=settings.s3_presign_ttl,
    )


def presign_get(key: str) -> str:
    """Browser GETs the file (video/pdf playback) from this URL."""
    return _public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_presign_ttl,
    )


def get_bytes(key: str) -> bytes:
    """Server-side download (worker extraction). Direct, no presign."""
    obj = _internal_client().get_object(Bucket=settings.s3_bucket, Key=key)
    return obj["Body"].read()
