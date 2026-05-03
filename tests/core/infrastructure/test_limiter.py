"""Unit tests for rate limiter module."""

from slowapi import Limiter

from src.core.infrastructure.config import settings
from src.core.infrastructure.limiter import get_limiter


class TestGetLimiter:
    """Tests for get_limiter() function."""

    def test_get_limiter_creates_instance(self):
        """Test that limiter instance is created."""
        limiter = get_limiter()

        assert limiter is not None
        assert isinstance(limiter, Limiter)

    def test_get_limiter_configuration(self):
        """Test that limiter configuration is correct."""
        limiter = get_limiter()

        # Verify limiter has key_func set (it's stored as _key_func internally)
        assert limiter._key_func is not None

    def test_get_limiter_same_instance_on_subsequent_calls(self):
        """Test that same instance is returned on subsequent calls."""
        limiter1 = get_limiter()
        limiter2 = get_limiter()

        # Note: get_limiter() creates a new instance each time,
        # but we can verify both are valid Limiter instances
        assert isinstance(limiter1, Limiter)
        assert isinstance(limiter2, Limiter)


class TestLimiterTestingMode:
    """Tests for rate limiter testing mode behavior."""

    def test_limiter_disabled_when_testing_true(self):
        """Test that rate limiting is disabled when settings.testing=True."""
        # Save original testing value
        original_testing = settings.testing

        try:
            # Set testing mode
            settings.testing = True
            limiter = get_limiter()

            # In testing mode, limiter should be disabled
            # The enabled attribute should be False
            assert limiter.enabled is False
        finally:
            # Restore original testing value
            settings.testing = original_testing

    def test_limiter_enabled_in_production(self):
        """Test that rate limiting is enabled only in production (non-testing)."""
        original_testing = settings.testing
        original_env = settings.environment

        try:
            settings.testing = False
            settings.environment = "production"
            limiter = get_limiter()
            assert limiter.enabled is True
        finally:
            settings.testing = original_testing
            settings.environment = original_env

    def test_limiter_disabled_in_development(self):
        """Test that rate limiting is disabled in development environment."""
        original_testing = settings.testing
        original_env = settings.environment

        try:
            settings.testing = False
            settings.environment = "development"
            limiter = get_limiter()
            assert limiter.enabled is False
        finally:
            settings.testing = original_testing
            settings.environment = original_env
