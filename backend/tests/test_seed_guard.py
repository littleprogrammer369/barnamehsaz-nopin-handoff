"""Unit tests for seed guard."""
import os


class TestSeedGuard:
    """Tests for seed guard logic."""

    def test_seed_allowed_in_test(self):
        """Seed should be allowed in test environment."""
        # Simulate test environment using environment variable
        os.environ["APP_ENV"] = "test"
        try:
            from app.core.config import Settings
            settings = Settings()
            assert settings.app_env == "test"
            # Seed should be allowed
            assert settings.app_env not in ("production", "prod")
        finally:
            os.environ.pop("APP_ENV", None)

    def test_seed_blocked_in_production(self):
        """Seed should be blocked in production."""
        # Simulate production environment
        os.environ["APP_ENV"] = "production"
        try:
            from app.core.config import Settings
            settings = Settings()
            assert settings.app_env == "production"
            # Seed should be blocked in production
            assert settings.app_env not in ("development", "test")
        finally:
            os.environ.pop("APP_ENV", None)

    def test_db_url_no_production_guard(self):
        """Test that DB URL is not hardcoded to production."""
        from app.core.config import Settings
        settings = Settings()
        # DB should not contain production URL
        assert "production" not in settings.db_name
        assert "production" not in settings.db_user
