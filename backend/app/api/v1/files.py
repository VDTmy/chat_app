"""
/api/v1/files — file upload endpoint.
"""

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.file_service import FileService

router = APIRouter(prefix="/api/v1/files", tags=["files"])


# ── POST /upload ───────────────────────────────────────────────────────────────
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a file to MinIO and return its presigned URL.

    Accepts multipart/form-data with a single ``file`` field.

    Restrictions:
    - Max size: 10 MB
    - Allowed types: image/jpeg, image/png, image/gif, video/mp4, application/pdf

    Returns::

        {
            "file_url":   "<presigned-get-url>",
            "file_name":  "<original filename>",
            "file_type":  "<MIME type>",
            "file_size":  <bytes as int>
        }
    """
    service = FileService()
    result = await service.upload_file(file, folder=f"users/{current_user.id}")
    return {
        "file_url": result["file_url"],
        "file_name": result["file_name"],
        "file_type": result["file_type"],
        "file_size": result["file_size"],
    }
