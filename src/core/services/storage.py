"""Storage abstraction layer for file storage providers."""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from uuid import uuid4

import aioboto3
from botocore.exceptions import ClientError

from src.core.infrastructure.config import settings


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file and return its identifier/URL.

        Args:
            file_content: Binary content of the file
            file_name: Original file name
            content_type: MIME type of the file (optional)

        Returns:
            File identifier or URL
        """
        pass

    @abstractmethod
    async def get_file_url(self, file_identifier: str) -> str:
        """
        Get a URL to access the file.

        Args:
            file_identifier: Identifier returned from upload_file

        Returns:
            URL to access the file
        """
        pass

    @abstractmethod
    async def delete_file(self, file_identifier: str) -> bool:
        """
        Delete a file.

        Args:
            file_identifier: Identifier returned from upload_file

        Returns:
            True if deleted successfully, False otherwise
        """
        pass


class S3StorageProvider(StorageProvider):
    """AWS S3 storage provider implementation."""

    def __init__(
        self,
        bucket_name: str,
        region: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        """
        Initialize S3 storage provider.

        Args:
            bucket_name: S3 bucket name
            region: AWS region
            access_key_id: AWS access key ID (optional, can use IAM role)
            secret_access_key: AWS secret access key (optional, can use IAM role)
            endpoint_url: Custom endpoint URL (optional, for MinIO/S3-compatible)
        """
        self.bucket_name = bucket_name
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url
        self.session = aioboto3.Session()

    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: Optional[str] = None
    ) -> str:
        """Upload file to S3."""
        # Generate unique file key
        file_extension = Path(file_name).suffix
        file_key = f"{uuid4()}{file_extension}"

        client_kwargs = {
            "region_name": self.region,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        async with self.session.client(  # type: ignore[attr-defined]
            "s3", **client_kwargs
        ) as s3:
            upload_kwargs = {
                "Bucket": self.bucket_name,
                "Key": file_key,
                "Body": file_content,
            }
            if content_type:
                upload_kwargs["ContentType"] = content_type

            await s3.put_object(**upload_kwargs)

        return file_key

    async def get_file_url(self, file_identifier: str) -> str:
        """Generate presigned URL for S3 object."""
        client_kwargs = {
            "region_name": self.region,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        async with self.session.client(  # type: ignore[attr-defined]
            "s3", **client_kwargs
        ) as s3:
            try:
                # Generate presigned URL (valid for 1 hour)
                url = await s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket_name, "Key": file_identifier},
                    ExpiresIn=3600,
                )
                return url
            except ClientError as e:
                raise ValueError(f"Failed to generate URL for {file_identifier}: {e}")

    async def delete_file(self, file_identifier: str) -> bool:
        """
        Delete file from S3.

        Returns True if deletion succeeded or file didn't exist (idempotent behavior).
        """
        client_kwargs = {
            "region_name": self.region,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        async with self.session.client(  # type: ignore[attr-defined]
            "s3", **client_kwargs
        ) as s3:
            try:
                await s3.delete_object(Bucket=self.bucket_name, Key=file_identifier)
                # S3 delete_object is idempotent - returns success even if missing
                return True
            except ClientError:
                return False


class LocalStorageProvider(StorageProvider):
    """Local file system storage provider (for development/testing)."""

    def __init__(self, storage_path: str = "./storage"):
        """
        Initialize local storage provider.

        Args:
            storage_path: Directory path for storing files
        """
        self.storage_path = Path(storage_path).resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _validate_file_path(self, file_identifier: str) -> Path:
        """
        Validate that file path stays within storage directory.

        Args:
            file_identifier: File identifier/key

        Returns:
            Validated Path object

        Raises:
            ValueError: If path traversal detected
        """
        # Prevent path traversal by checking for actual traversal sequences
        # Allow ".." in filenames (e.g., "file..txt" or "{uuid}..")
        # but not "../", "..\\", "/..", "\\..", or paths ending in "/.." or "\\.."
        # Block identifiers starting with ".." to prevent confusion

        # Check for path traversal patterns
        # 1. Contains "../" or "..\\" anywhere (path traversal with forward slash)
        # 2. Contains "/../" or "\\..\\" (path traversal in middle)
        # 3. Starts with "/" or "\\" (absolute paths)
        # 4. Starts with "../" or "..\\" (relative traversal)
        # 5. Starts with ".." (prevents "..file.txt" confusion)
        # 6. Ends with "/.." or "\\.." (traversal without trailing slash)
        # 7. Contains "/.." or "\\.." as path component (catches "subdir/..")
        # Note: We allow filenames ending in ".." but not path components
        if (
            "../" in file_identifier
            or "..\\" in file_identifier
            or file_identifier.startswith("/")
            or file_identifier.startswith("\\")
            or "/../" in file_identifier
            or "\\..\\" in file_identifier
            or file_identifier.startswith("../")
            or file_identifier.startswith("..\\")
            or file_identifier.startswith("..")
            or file_identifier.endswith("/..")
            or file_identifier.endswith("\\..")
            or "/.." in file_identifier
            or "\\.." in file_identifier
        ):
            raise ValueError(
                f"Path traversal detected: {file_identifier} "
                f"contains invalid path components"
            )

        # Resolve the full path
        file_path = (self.storage_path / file_identifier).resolve()

        # Check that resolved path is within storage directory
        try:
            file_path.relative_to(self.storage_path)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: {file_identifier} "
                f"resolves outside storage directory"
            )

        return file_path

    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: Optional[str] = None
    ) -> str:
        """Upload file to local storage."""
        # Generate unique file name
        file_extension = Path(file_name).suffix
        file_key = f"{uuid4()}{file_extension}"
        file_path = self.storage_path / file_key

        # Run blocking file write in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, file_path.write_bytes, file_content)
        return file_key

    async def get_file_url(self, file_identifier: str) -> str:
        """Return HTTP URL for local file (to be served by FastAPI static files)."""
        file_path = self._validate_file_path(file_identifier)
        # Run blocking file system checks in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, file_path.exists)
        if not exists:
            raise ValueError(f"File not found: {file_identifier}")
        # Ensure the path is a file, not a directory
        is_dir = await loop.run_in_executor(None, file_path.is_dir)
        if is_dir:
            raise ValueError(f"Path is a directory, not a file: {file_identifier}")
        # Return HTTP URL that will be served by FastAPI static file serving
        # The actual static file mount will be configured in main.py
        return f"/static/{file_identifier}"

    async def delete_file(self, file_identifier: str) -> bool:
        """
        Delete file from local storage.

        Returns True if file was deleted or didn't exist (idempotent behavior
        to match S3StorageProvider).
        """
        # Validate path first (raises ValueError if path traversal detected)
        file_path = self._validate_file_path(file_identifier)
        # Run blocking file system operations in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        try:
            exists = await loop.run_in_executor(None, file_path.exists)
            if exists:
                await loop.run_in_executor(None, file_path.unlink)
            # Return True even if file didn't exist (idempotent, matches S3 behavior)
            return True
        except OSError:
            return False


def get_storage_provider() -> StorageProvider:
    """
    Factory function to get storage provider based on configuration.

    Returns:
        StorageProvider instance configured from settings
    """
    if settings.storage_provider == "s3":
        if not settings.aws_s3_bucket_name:
            raise ValueError("AWS_S3_BUCKET_NAME must be set when using S3 storage")
        return S3StorageProvider(
            bucket_name=settings.aws_s3_bucket_name,
            region=settings.aws_region,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.aws_s3_endpoint_url,
        )
    else:  # local
        return LocalStorageProvider(storage_path=settings.local_storage_path)
