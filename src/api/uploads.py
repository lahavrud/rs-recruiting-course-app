"""HTTP upload guard — the FastAPI-facing wrapper over file validation.

Lives in the API layer (not `core/services/file_validation.py`) so the domain
stays framework-free: the worker never handles `UploadFile`, so pulling FastAPI
into the shared validation module would needlessly bloat the worker image. The
pure, bytes-in magic-byte checks remain in `core/services/file_validation.py`
and are shared by both services.
"""

from fastapi import HTTPException, UploadFile


async def validate_upload(
    file: UploadFile,
    allowed_types: set[str],
    max_bytes: int,
) -> bytes:
    """Validate content type and size; return file bytes on success.

    Raises HTTPException 422 for disallowed MIME type, 413 for oversized file.
    """
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=422, detail="unsupported_file_type")
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="file_too_large")
    return content
