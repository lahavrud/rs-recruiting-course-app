"""Security tests for storage providers."""

import pytest

from src.core.storage import LocalStorageProvider


class TestLocalStorageProviderSecurity:
    """Security tests for LocalStorageProvider."""

    @pytest.fixture
    def provider(self, tmp_path):
        """Create a LocalStorageProvider instance with temp directory."""
        return LocalStorageProvider(storage_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_path_traversal_get_file_url(self, provider: LocalStorageProvider):
        """Test that path traversal is prevented in get_file_url."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_delete_file(self, provider: LocalStorageProvider):
        """Test that path traversal is prevented in delete_file."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.delete_file("../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_multiple_levels(self, provider: LocalStorageProvider):
        """Test that multiple levels of path traversal are prevented."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("../../../../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_encoded(self, provider: LocalStorageProvider):
        """Test that encoded path traversal sequences are prevented."""
        # Test with URL-encoded sequences (decoded: ../../../etc/passwd)
        # The validation checks for ".." in the identifier, so encoded won't match
        # But we should still validate the resolved path
        import urllib.parse

        decoded = urllib.parse.unquote("%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd")
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url(decoded)

    @pytest.mark.asyncio
    async def test_valid_path_within_storage(self, provider: LocalStorageProvider):
        """Test that valid paths within storage directory work correctly."""
        # Upload a file
        file_content = b"test content"
        file_key = await provider.upload_file(file_content, "test.txt")

        # Should work fine
        url = await provider.get_file_url(file_key)
        assert url.startswith("/static/")

        # Delete should work
        result = await provider.delete_file(file_key)
        assert result is True

    @pytest.mark.asyncio
    async def test_file_with_double_dots_in_name(self, provider: LocalStorageProvider):
        """Test that files with '..' in the filename (not path traversal) work."""
        # Files like "test.txt.." or "file...." should be allowed
        # Even if the file_key contains ".." (e.g., from suffix extraction),
        # it should be accessible as long as it's not actual path traversal
        file_content = b"test content with dots"

        # Test file ending in ".." - upload and verify it works
        file_key1 = await provider.upload_file(file_content, "test.txt..")
        # Should be able to retrieve it (no path traversal error)
        url1 = await provider.get_file_url(file_key1)
        assert url1.startswith("/static/")

        # Should be able to delete it
        result1 = await provider.delete_file(file_key1)
        assert result1 is True

        # Test file with multiple dots
        file_key2 = await provider.upload_file(file_content, "file....")
        # Should be able to retrieve and delete without path traversal error
        url2 = await provider.get_file_url(file_key2)
        assert url2.startswith("/static/")
        result2 = await provider.delete_file(file_key2)
        assert result2 is True

        # Test file with ".." in the middle of the name
        file_key3 = await provider.upload_file(file_content, "file..name.txt")
        # Should work fine - ".." is part of filename, not path traversal
        url3 = await provider.get_file_url(file_key3)
        assert url3.startswith("/static/")
        result3 = await provider.delete_file(file_key3)
        assert result3 is True

        # Test that a file_key ending in ".." is accessible
        # This simulates the reported bug where files with ".." extension
        # become inaccessible
        # Create a file directly with a key ending in ".."
        # (simulating Path('test.txt..').suffix = "..")
        from uuid import uuid4

        test_key_with_dots = f"{uuid4()}.."
        test_file_path = provider.storage_path / test_key_with_dots
        test_file_path.write_bytes(file_content)

        # Should be able to access it (this was the bug - it was being blocked)
        url4 = await provider.get_file_url(test_key_with_dots)
        assert url4.startswith("/static/")

        # Should be able to delete it
        result4 = await provider.delete_file(test_key_with_dots)
        assert result4 is True

    @pytest.mark.asyncio
    async def test_path_traversal_still_blocked(self, provider: LocalStorageProvider):
        """Test that actual path traversal is still blocked."""
        # These should still be blocked (actual path traversal)
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("../etc/passwd")

        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("../../secret.txt")

        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.delete_file("../etc/passwd")

        # Starting with ".." should be blocked
        # (prevents confusion with parent directory)
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("..file.txt")

        # Path traversal in middle should be blocked
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("some/path/../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_ending_with_dotdot(
        self, provider: LocalStorageProvider
    ):
        """Test paths ending in '/..' or '\\..' are blocked (reported vulnerability)."""
        # Paths ending in "/.." should be blocked (resolves to directory, not file)
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("subdir/..")

        # Windows-style path traversal ending
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("subdir\\..")

        # Path traversal ending in middle of path
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("some/subdir/..")

        # Multiple levels ending in traversal
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("level1/level2/..")

        # Test delete_file also blocks these
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.delete_file("subdir/..")

    @pytest.mark.asyncio
    async def test_valid_filenames_with_dots_still_work(
        self, provider: LocalStorageProvider
    ):
        """Test that valid filenames ending in '..' still work (not path traversal)."""
        file_content = b"test content"

        # Filename ending in ".." should work (no separator before dots)
        file_key1 = await provider.upload_file(file_content, "test..")
        url1 = await provider.get_file_url(file_key1)
        assert url1.startswith("/static/")
        await provider.delete_file(file_key1)

        # Filename with ".." in middle should work
        file_key2 = await provider.upload_file(file_content, "file..name.txt")
        url2 = await provider.get_file_url(file_key2)
        assert url2.startswith("/static/")
        await provider.delete_file(file_key2)

        # UUID with ".." extension should work
        from uuid import uuid4

        test_key = f"{uuid4()}.."
        test_file_path = provider.storage_path / test_key
        test_file_path.write_bytes(file_content)
        url3 = await provider.get_file_url(test_key)
        assert url3.startswith("/static/")
        await provider.delete_file(test_key)

    @pytest.mark.asyncio
    async def test_directory_path_blocked_in_get_file_url(
        self, provider: LocalStorageProvider
    ):
        """Test that get_file_url correctly identifies and blocks directory paths."""
        # Create a subdirectory in storage
        subdir = provider.storage_path / "subdir"
        subdir.mkdir(exist_ok=True)

        # Even if a path resolves to a directory (not a file), it should be blocked
        # This tests the is_dir() check in get_file_url
        # Note: The path traversal check should catch "subdir/.." before we get here
        # But we also test that directories are not treated as files
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_file_url("subdir/..")
