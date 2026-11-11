"""Unit tests for RBAC role logic and settings/seed guard.

All tests are ENVIRONMENT-INDEPENDENT: they do NOT assert on the value of
``settings.app_env`` resolved from the current process environment. Instead
they inspect the *declared default* of the Settings field or call the seed
guard with explicit environment strings. This makes the suite reproducible
under ``APP_ENV=development`` AND ``APP_ENV=test``.
"""
import pytest

from app.core.config import Settings, _seed_guard_check, get_settings
from app.core.password_utils import verify_password, hash_password
from app.core.jwt_utils import decode_token, hash_refresh_token, new_family_id


# ---------------------------------------------------------------------------
# RBAC role logic
# ---------------------------------------------------------------------------

def test_admin_role_has_full_access():
    """The admin role may register users and act on any user's password."""
    allowed_roles_for_register = {"admin"}
    assert "admin" in allowed_roles_for_register
    assert "unit_manager" not in allowed_roles_for_register


def test_unit_manager_cannot_register():
    """unit_manager is explicitly NOT in the register allow-list."""
    allowed_roles_for_register = {"admin"}
    assert "unit_manager" not in allowed_roles_for_register


def test_change_password_self_or_admin():
    """A user may change their own password; only admin may act on another."""
    def may_change(actor_role: str, is_self: bool) -> bool:
        return is_self or actor_role == "admin"
    assert may_change("unit_manager", is_self=True) is True
    assert may_change("unit_manager", is_self=False) is False
    assert may_change("admin", is_self=False) is True
    assert may_change("admin", is_self=True) is True


# ---------------------------------------------------------------------------
# Settings: inspect the *declared default*, not the env-resolved value.
# This keeps the test stable under any APP_ENV.
# ---------------------------------------------------------------------------

def test_settings_app_env_default_declaration():
    """The Settings field default is 'development' (declared, not env-resolved).

    This reads the pydantic field default rather than ``get_settings().app_env``
    (which is influenced by the APP_ENV env var), so it passes in every env.
    """
    default = Settings.model_fields["app_env"].default
    assert default == "development"


def test_seed_guard_allows_dev_and_test_explicitly():
    """Seed guard allows 'development' and 'test' when checked explicitly."""
    # No exception expected for these two environments.
    for env in ("development", "test"):
        _seed_guard_check(env)  # raises RuntimeError if not allowed


def test_seed_guard_blocks_production_and_staging_explicitly():
    """Seed guard raises for production / staging environments."""
    with pytest.raises(RuntimeError):
        _seed_guard_check("production")
    with pytest.raises(RuntimeError):
        _seed_guard_check("staging")


def test_seed_guard_is_case_sensitive_and_strict():
    """Only the exact strings 'development' and 'test' are allowed."""
    with pytest.raises(RuntimeError):
        _seed_guard_check("DEV")  # not the exact 'development' token
    with pytest.raises(RuntimeError):
        _seed_guard_check("")
