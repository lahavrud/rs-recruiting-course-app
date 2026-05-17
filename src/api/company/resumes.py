"""Resume download endpoint — streams bytes from local storage or S3."""

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response

from src.core.infrastructure.config import settings
from src.core.infrastructure.dependencies import get_current_admin
from src.core.services.storage import get_storage_provider
from src.models import User

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

# UUID key + extension — no slashes allowed, only safe filename characters
_SAFE_KEY = re.compile(r"^[\w.\-]+$")


@router.get("/{file_key}")
async def download_resume(
    file_key: str,
    _: User = Depends(get_current_admin),
) -> Response:
    """Download a candidate resume.

    Acts as a secure proxy: fetches the file from local storage or S3
    and streams the raw bytes directly. Avoids cross-origin S3 redirects.
    Requires admin authentication.
    """
    if not _SAFE_KEY.match(file_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file key",
        )

    storage = get_storage_provider()

    # Storage layout: every uploaded resume lives under the `resumes/`
    # subdirectory (local) or under the `resumes/` key prefix (S3) — see
    # LocalStorageProvider.upload_file and applications._validate_and_upload_resume.
    # The frontend strips that prefix when calling this route (the path-param
    # regex doesn't allow slashes), so we re-add it here.
    storage_key = f"resumes/{file_key}"

    if settings.storage_provider == "local":
        storage_root = Path(settings.local_storage_path).resolve()
        file_path = (storage_root / storage_key).resolve()
        # Ensure resolved path stays inside the storage directory
        try:
            file_path.relative_to(storage_root)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file key",
            )
        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        return FileResponse(path=file_path, filename=file_key)

    try:
        file_bytes = await storage.download_file(storage_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from e
    content_type, _ = mimetypes.guess_type(file_key)
    if not content_type:
        content_type = "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{file_key}"'},
    )
