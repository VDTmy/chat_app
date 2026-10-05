"""
FileService — upload files to MinIO and generate presigned URLs.

Validation rules:
  - Max size: 10 MB
  - Allowed MIME types: image/jpeg, image/png, image/gif, video/mp4, application/pdf
"""

import io
import uuid
from datetime import timedelta

from fastapi import HTTPException, UploadFile, status
from minio import Minio

try:
    from minio import S3Error  # minio >= 7.x
except ImportError:
    from minio.error import S3Error  # type: ignore[no-redef]  # minio < 7.x

from app.core.config import settings

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "video/mp4": "mp4",
    "application/pdf": "pdf",
}


def _get_minio_client() -> Minio:
    """Return a configured MinIO client (synchronous SDK)."""
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def ensure_bucket_exists() -> None:
    """Create the bucket if it doesn't already exist. Called at startup."""
    client = _get_minio_client()
    try:
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
    except S3Error as exc:
        # Log but don't crash the server if MinIO isn't ready yet
        print(f"[FileService] Could not ensure bucket exists: {exc}")


class FileService:
    """Service for uploading files to MinIO and generating presigned URLs."""

    def __init__(self) -> None:
        self._client = _get_minio_client()
        self._bucket = settings.MINIO_BUCKET

    # ── Validation ─────────────────────────────────────────────────────────────

    @staticmethod
    def _validate(file: UploadFile, data: bytes) -> None:
        """Raise HTTP 400/413 if the file fails validation checks."""
        content_type = file.content_type or ""

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File type '{content_type}' không được phép. "
                    f"Cho phép: {', '.join(ALLOWED_CONTENT_TYPES.keys())}"
                ),
            )

        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File vượt quá giới hạn 10 MB.",
            )

    # ── Upload ─────────────────────────────────────────────────────────────────

    async def upload_file(self, file: UploadFile, folder: str = "uploads") -> dict:
        """Upload *file* to MinIO under *folder*.

        Returns a dict with ``object_name``, ``file_url``, ``file_name``,
        ``file_type``, and ``file_size``.
        """
        data = await file.read()
        self._validate(file, data)

        content_type = file.content_type or "application/octet-stream"
        ext = ALLOWED_CONTENT_TYPES.get(content_type, "bin")
        object_name = f"{folder}/{uuid.uuid4()}.{ext}"

        # Upload via synchronous MinIO SDK (runs in the current event loop thread;
        # acceptable for file uploads which are fast I/O on a local container).
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

        file_url = self.generate_presigned_url(object_name)

        return {
            "object_name": object_name,
            "file_url": file_url,
            "file_name": file.filename or object_name.split("/")[-1],
            "file_type": content_type,
            "file_size": len(data),
        }

    # ── Presigned URL ──────────────────────────────────────────────────────────

    def generate_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """Return a presigned GET URL valid for *expires* seconds."""
        url = self._client.presigned_get_object(
            bucket_name=self._bucket,
            object_name=object_name,
            expires=timedelta(seconds=expires),
        )
        return url
