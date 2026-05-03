"""Local filesystem storage provider (development / testing)."""

import asyncio
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.core.services.storage import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem under a configurable directory."""

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path).resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, file_identifier: str) -> Path:
        """Resolve and validate that the path stays inside storage_path."""
        if (
            "../" in file_identifier
            or "..\\" in file_identifier
            or file_identifier.startswith("/")
            or file_identifier.startswith("\\")
            or file_identifier.startswith("..")
            or "/.." in file_identifier
            or "\\.." in file_identifier
        ):
            raise ValueError(
                f"Path traversal detected in identifier: {file_identifier!r}"
            )
        resolved = (self.storage_path / file_identifier).resolve()
        try:
            resolved.relative_to(self.storage_path)
        except ValueError:
            raise ValueError(
                f"Identifier {file_identifier!r} resolves outside storage directory"
            )
        return resolved

    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: Optional[str] = None
    ) -> str:
        file_key = f"{uuid4()}{Path(file_name).suffix}"
        file_path = self.storage_path / file_key
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, file_path.write_bytes, file_content)
        return file_key

    async def get_file_url(self, file_identifier: str) -> str:
        file_path = self._safe_path(file_identifier)
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, file_path.exists)
        if not exists:
            raise ValueError(f"File not found: {file_identifier}")
        if await loop.run_in_executor(None, file_path.is_dir):
            raise ValueError(f"Identifier is a directory: {file_identifier}")
        return f"/static/{file_identifier}"

    async def download_file(self, file_identifier: str) -> bytes:
        file_path = self._safe_path(file_identifier)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, file_path.read_bytes)

    async def delete_file(self, file_identifier: str) -> bool:
        file_path = self._safe_path(file_identifier)  # raises ValueError on traversal
        loop = asyncio.get_event_loop()
        try:
            exists = await loop.run_in_executor(None, file_path.exists)
            if exists:
                await loop.run_in_executor(None, file_path.unlink)
            return True
        except OSError:
            return False
