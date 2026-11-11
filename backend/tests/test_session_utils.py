"""Unit tests for refresh token helpers (hashing, claims, rotation primitives)."""
import pytest
from app.core.jwt_utils import (
    create_refresh_token,
    create_access_token,
    decode_token,
    hash_refresh_token,
    new_family_id,
)


class TestRefreshTokenHelpers:
    """Pure unit tests that don't require a database."""

    def test_hash_is_deterministic(self):
        """Same token -> same SHA-256 digest (hex, 64 chars)."""
        tok = create_refresh_token({"sub": "1"})
        h = hash_refresh_token(tok)
        assert len(h) == 64
        assert hash_refresh_token(tok) == h

    def test_hash_differs_per_token(self):
        """Different tokens produce different digests."""
        a = hash_refresh_token(create_refresh_token({"sub": "1"}, family_id=new_family_id()))
        b = hash_refresh_token(create_refresh_token({"sub": "1"}, family_id=new_family_id()))
        assert a != b

    def test_refresh_token_has_jti_and_family(self):
        """Refresh tokens carry unique jti and the given family."""
        fam = new_family_id()
        t1 = create_refresh_token({"sub": "1"}, family_id=fam)
        p1 = decode_token(t1)
        t2 = create_refresh_token({"sub": "1"}, family_id=fam)
        p2 = decode_token(t2)
        assert p1["type"] == "refresh"
        assert p1["jti"] == p2["jti"] or p1["jti"] != p2["jti"]
        assert p1["family"] == fam and p2["family"] == fam
        assert p1["jti"] != p2["jti"]  # each rotation is a unique jti

    def test_access_token_not_usable_as_refresh(self):
        """An access token has type=access and no family; refresh logic rejects it."""
        at = create_access_token({"sub": "1"})
        p = decode_token(at)
        assert p["type"] == "access"
        assert "family" not in p

    def test_invalid_token_decodes_to_none(self):
        assert decode_token("garbage") is None

