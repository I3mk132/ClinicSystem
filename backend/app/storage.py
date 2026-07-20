"""
Cloudflare R2 object storage (Session 4).

R2 speaks the S3 API, so we drive it with boto3's S3 client pointed at the R2
endpoint. The upload path is presigned-PUT: the backend signs a short-lived URL
scoped to one exact object key + content-type, the browser PUTs the bytes
straight to R2 (the file never transits the API), then confirms back so we can
persist a `MediaAsset` row.

Tenant isolation lives in the OBJECT KEY: every key is `clinics/{clinic_id}/...`
and the key is generated here, server-side, from the caller's resolved clinic -
never taken from the client. See `routers/media.py`.

R2 is optional: with no credentials configured the module reports `is_enabled()
== False` and the media endpoints return 503 rather than the app failing to
boot. boto3 is imported lazily so it isn't a hard dependency for running the
rest of the API.
"""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Optional

from app.core.config import settings

# Content-type -> file extension for the object key. Only these image types are
# accepted for upload (validated again when presigning).
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/webp": "webp",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}


def is_enabled() -> bool:
    """True only when enough R2 config is present to actually sign/upload."""
    return bool(
        settings.R2_ACCOUNT_ID
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET
        and settings.R2_PUBLIC_BASE_URL
    )


@lru_cache
def _client():
    """Cached boto3 S3 client aimed at this account's R2 endpoint."""
    import boto3
    from botocore.config import Config

    endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        # R2 ignores region but boto3 requires one; "auto" is the R2 convention.
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def build_object_key(clinic_id: int, content_type: str) -> str:
    """A unique, ALWAYS clinic-prefixed key. The clinic prefix is the isolation."""
    ext = ALLOWED_IMAGE_TYPES.get(content_type, "bin")
    return f"clinics/{clinic_id}/{uuid.uuid4().hex}.{ext}"


def public_url(object_key: str) -> str:
    return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{object_key}"


def presign_put(object_key: str, content_type: str) -> str:
    """
    A short-lived PUT URL scoped to exactly this key + content-type. The browser
    MUST send the same `Content-Type` header on the PUT or the signature fails.
    """
    return _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.MEDIA_PRESIGN_EXPIRE_SECONDS,
    )


def object_exists(object_key: str) -> bool:
    """Confirm the browser actually uploaded before we persist a MediaAsset row."""
    from botocore.exceptions import ClientError

    try:
        _client().head_object(Bucket=settings.R2_BUCKET, Key=object_key)
        return True
    except ClientError:
        return False


def delete_object(object_key: str) -> None:
    """Best-effort delete from R2 (the DB row is removed regardless by the caller)."""
    _client().delete_object(Bucket=settings.R2_BUCKET, Key=object_key)


def belongs_to_clinic(object_key: str, clinic_id: int) -> bool:
    """A key we accept from a client must sit under this clinic's prefix."""
    return object_key.startswith(f"clinics/{clinic_id}/")


def guess_content_type_from_key(object_key: str) -> Optional[str]:
    ext = object_key.rsplit(".", 1)[-1].lower() if "." in object_key else ""
    for ctype, e in ALLOWED_IMAGE_TYPES.items():
        if e == ext:
            return ctype
    return None
