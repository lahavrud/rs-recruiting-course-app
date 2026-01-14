"""Pytest configuration and fixtures for testing."""

import pytest


@pytest.fixture
def mock_s3_bucket():
    """Mock AWS S3 service using moto - returns bucket info for use in tests."""
    # Note: mock_s3() must be used as a context manager inside async tests
    # This fixture just provides the bucket configuration
    return {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
    }


@pytest.fixture
def mock_ses_identity():
    """Mock AWS SES service using moto - returns identity info for use in tests."""
    # Note: mock_ses() must be used as a context manager inside async tests
    # This fixture just provides the SES configuration
    return {
        "from_email": "test@example.com",
        "region": "us-east-1",
    }
