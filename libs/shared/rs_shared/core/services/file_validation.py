"""Magic byte validation for uploaded files.

Verifies that the actual file content matches the declared file type,
preventing extension-spoofing attacks (e.g. renaming malware.exe to resume.pdf).

Pure, framework-free functions over bytes — no FastAPI. The HTTP-facing upload
guard (`UploadFile` → bytes, size/MIME checks raising `HTTPException`) lives in
`services/api/rs_api/api/uploads.py` so the worker never imports the web stack.
"""

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"
_PDF = b"%PDF"
_DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_DOCX_ZIP = b"PK\x03\x04"

_IMAGE_SIGNATURES: dict[str, list[bytes]] = {
    "image/jpeg": [_JPEG],
    "image/png": [_PNG],
    "image/gif": [_GIF87, _GIF89],
    "image/webp": [],  # handled separately (RIFF....WEBP structure)
}


def is_valid_image_magic_bytes(data: bytes, declared_mime: str) -> bool:
    """Return True if the file header matches the declared image MIME type."""
    if not data:
        return False
    if declared_mime == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    sigs = _IMAGE_SIGNATURES.get(declared_mime, [])
    return any(data.startswith(sig) for sig in sigs)


def is_valid_document_magic_bytes(data: bytes, extension: str) -> bool:
    """Return True if the file header matches the declared document extension."""
    if not data:
        return False
    if extension == "pdf":
        return data.startswith(_PDF)
    if extension == "doc":
        return data.startswith(_DOC)
    if extension == "docx":
        return data.startswith(_DOCX_ZIP)
    return False
