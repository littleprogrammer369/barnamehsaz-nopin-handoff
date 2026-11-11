from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    api_prefix: str = "/api/v1"

    # Database
    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "barnamehsaz_novin_dev"
    db_user: str = "barnamehsaz"
    db_password: str = "change_me_local"

    # Security
    secret_key: str = "change_me_in_production"
    access_token_expire_minutes: int = 30
    session_timeout_minutes: int = 30
    pass_min_length: int = 8
    password_hash: str = "argon2id"

    # OTP
    otp_expiry_minutes: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


def _seed_guard_check(app_env: str) -> None:
    """Allow demo seeding only in development / test environments.

    Raises ``RuntimeError`` for any other value (production, staging, ...).
    Kept as a small pure function so it can be unit-tested in isolation
    without touching process environment variables.
    """
    if app_env not in ("development", "test"):
        raise RuntimeError(
            f"Seeding is not allowed in app_env={app_env!r} "
            "(only 'development' and 'test' are permitted)"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
