"""Shared resume-streaming helper used by both admin and candidate-facing routes.

Both endpoints serve files stored under ``resumes/<basename>`` either on local
disk or in S3; the difference is purely access control (admin authorizes by
role, candidate by ownership of the parent ``Application``). This helper
centralizes the MIME-type lookup, the safe-basename guard, and the
storage-provider branching so the route handlers stay focused on auth + the
DB lookup that proves the request is authorized to see this particular file.
"""

import re
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse, Response

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.services.storage import get_storage_provider

# Storage keys are constructed as ``resumes/<basename>``; the basename portion
# must not contain slashes or path-traversal sequences. Defends against
# Application.resume_path values that — were the DB ever compromised —
# pointed outside the resumes/ prefix.
_SAFE_KEY = re.compile(r"^[\w.\-]+$")

_MIME_BY_EXT: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
}


def _content_type(file_key: str) -> str:
    ext = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


def basename_from_storage_key(storage_key: str) -> str:
    """Strip the ``resumes/`` (or any) prefix and return the bare filename."""
    return storage_key.rsplit("/", 1)[-1]


async def stream_resume(file_key: str) -> Response:
    """Return a Response streaming the resume identified by ``file_key``.

    ``file_key`` is the basename (e.g. ``abc123.pdf``); the storage key it
    resolves to is ``resumes/{file_key}``. Raises HTTPException(400) for
    unsafe keys and HTTPException(404) when the underlying file is missing.
    """
    if not _SAFE_KEY.match(file_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_file_key"
        )

    content_type = _content_type(file_key)
    disposition = "inline" if content_type == "application/pdf" else "attachment"
    storage_key = f"resumes/{file_key}"

    if settings.storage_provider == "local":
        storage_root = Path(settings.local_storage_path).resolve()
        file_path = (storage_root / storage_key).resolve()
        try:
            file_path.relative_to(storage_root)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_file_key"
            ) from exc
        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="file_not_found"
            )
        return FileResponse(
            path=file_path,
            media_type=content_type,
            content_disposition_type=disposition,
            filename=file_key,
        )

    storage = get_storage_provider()
    try:
        file_bytes = await storage.download_file(storage_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="file_not_found"
        ) from e
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{file_key}"'},
    )
