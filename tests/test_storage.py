"""Tests for storage service."""

import tempfile

import pytest

from src.core.config import settings
from src.core.storage import (
    LocalStorageProvider,
    S3StorageProvider,
    get_storage_provider,
)


class TestLocalStorageProvider:
    """Tests for LocalStorageProvider."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def provider(self, temp_dir):
        """Create a LocalStorageProvider instance."""
        return LocalStorageProvider(storage_path=temp_dir)

    @pytest.mark.asyncio
    async def test_upload_file(self, provider: LocalStorageProvider):
        """Test file upload."""
        file_content = b"test file content"
        file_name = "test.txt"

        file_key = await provider.upload_file(file_content, file_name)

        assert file_key is not None
        assert file_key.endswith(".txt")
        # Verify file exists
        file_path = provider.storage_path / file_key
        assert file_path.exists()
        assert file_path.read_bytes() == file_content

    @pytest.mark.asyncio
    async def test_get_file_url(self, provider: LocalStorageProvider):
        """Test getting file URL."""
        file_content = b"test content"
        file_name = "test.txt"

        file_key = await provider.upload_file(file_content, file_name)
        url = await provider.get_file_url(file_key)

        assert url is not None
        # Should return HTTP URL path, not filesystem path
        assert url.startswith("/static/")
        assert file_key in url
        # Verify file exists on filesystem
        file_path = provider.storage_path / file_key
        assert file_path.exists()
        assert file_path.read_bytes() == file_content

    @pytest.mark.asyncio
    async def test_get_file_url_not_found(self, provider: LocalStorageProvider):
        """Test getting URL for non-existent file."""
        with pytest.raises(ValueError, match="File not found"):
            await provider.get_file_url("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_file(self, provider: LocalStorageProvider):
        """Test file deletion."""
        file_content = b"test content"
        file_name = "test.txt"

        file_key = await provider.upload_file(file_content, file_name)
        file_path = provider.storage_path / file_key
        assert file_path.exists()

        result = await provider.delete_file(file_key)
        assert result is True
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, provider: LocalStorageProvider):
        """Test deleting non-existent file (idempotent - returns True)."""
        result = await provider.delete_file("nonexistent.txt")
        # Both S3 and Local providers return True for non-existent files (idempotent)
        assert result is True

    @pytest.mark.asyncio
    async def test_upload_with_content_type(self, provider: LocalStorageProvider):
        """Test file upload with content type."""
        file_content = b"<html><body>Test</body></html>"
        file_name = "test.html"

        file_key = await provider.upload_file(
            file_content, file_name, content_type="text/html"
        )

        assert file_key is not None
        assert file_key.endswith(".html")


class TestS3StorageProvider:
    """Tests for S3StorageProvider using AsyncMock (moto doesn't support aioboto3)."""

    @pytest.mark.asyncio
    async def test_upload_file(self, mock_s3_bucket):
        """Test S3 file upload using mocked S3 client."""
        from unittest.mock import AsyncMock, patch

        provider = S3StorageProvider(
            bucket_name=mock_s3_bucket["bucket_name"],
            region=mock_s3_bucket["region"],
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        file_content = b"test file content"
        file_name = "test.txt"

        # Mock the S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.put_object = AsyncMock()

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3_client

            file_key = await provider.upload_file(file_content, file_name)
            assert file_key is not None
            assert file_key.endswith(".txt")

            # Verify put_object was called
            mock_s3_client.put_object.assert_called_once()
            call_kwargs = mock_s3_client.put_object.call_args[1]
            assert call_kwargs["Bucket"] == mock_s3_bucket["bucket_name"]
            assert call_kwargs["Body"] == file_content

    @pytest.mark.asyncio
    async def test_get_file_url(self, mock_s3_bucket):
        """Test getting S3 presigned URL using mocked S3 client."""
        from unittest.mock import AsyncMock, patch

        provider = S3StorageProvider(
            bucket_name=mock_s3_bucket["bucket_name"],
            region=mock_s3_bucket["region"],
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        file_key = "test-file-key.txt"
        expected_url = "https://test-bucket.s3.amazonaws.com/test-file-key.txt"

        # Mock the S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.generate_presigned_url = AsyncMock(return_value=expected_url)

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3_client

            url = await provider.get_file_url(file_key)

            assert url == expected_url
            mock_s3_client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_file(self, mock_s3_bucket):
        """Test S3 file deletion using mocked S3 client."""
        from unittest.mock import AsyncMock, patch

        provider = S3StorageProvider(
            bucket_name=mock_s3_bucket["bucket_name"],
            region=mock_s3_bucket["region"],
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        file_key = "test-file-key.txt"

        # Mock the S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.delete_object = AsyncMock()

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3_client

            result = await provider.delete_file(file_key)
            assert result is True

            # Verify delete_object was called
            mock_s3_client.delete_object.assert_called_once_with(
                Bucket=mock_s3_bucket["bucket_name"], Key=file_key
            )


class TestStorageProviderFactory:
    """Tests for storage provider factory function."""

    def test_get_storage_provider_local(self, monkeypatch):
        """Test getting local storage provider."""
        monkeypatch.setattr(settings, "storage_provider", "local")
        monkeypatch.setattr(settings, "local_storage_path", "./test_storage")

        provider = get_storage_provider()
        assert isinstance(provider, LocalStorageProvider)
        # storage_path is now resolved to absolute path
        assert provider.storage_path.is_absolute()
        assert "test_storage" in str(provider.storage_path)

    def test_get_storage_provider_s3(self, monkeypatch):
        """Test getting S3 storage provider."""
        monkeypatch.setattr(settings, "storage_provider", "s3")
        monkeypatch.setattr(settings, "aws_s3_bucket_name", "test-bucket")
        monkeypatch.setattr(settings, "aws_region", "us-east-1")

        provider = get_storage_provider()
        assert isinstance(provider, S3StorageProvider)
        assert provider.bucket_name == "test-bucket"

    def test_get_storage_provider_s3_missing_bucket(self, monkeypatch):
        """Test S3 provider requires bucket name."""
        monkeypatch.setattr(settings, "storage_provider", "s3")
        monkeypatch.setattr(settings, "aws_s3_bucket_name", None)

        with pytest.raises(ValueError, match="AWS_S3_BUCKET_NAME must be set"):
            get_storage_provider()
