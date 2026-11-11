"""Unit tests for password hashing utilities."""
import pytest
from app.core.password_utils import hash_password, verify_password


class TestPasswordUtils:
    """Tests for password hashing and verification."""

    def test_hash_and_verify_password(self):
        """Hash and verify round-trip."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > len(password)
        assert verify_password(password, hashed)

    def test_verify_wrong_password(self):
        """Wrong password should fail verification."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert not verify_password("WrongPassword", hashed)

    def test_verify_empty_password(self):
        """Empty password should fail verification."""
        assert not verify_password("", "$argon2id$")

    def test_hash_deterministic(self):
        """Same password should produce different hashes (salt).
        
        Note: Argon2 includes random salt by default, so hashes differ.
        """
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # Salt should make them different
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

    def test_password_length_minimum(self):
        """Minimum password length check."""
        with pytest.raises(ValueError):
            hash_password("short")

    def test_password_length_maximum(self):
        """Maximum password length check."""
        long_password = "a" * 129
        with pytest.raises(ValueError):
            hash_password(long_password)
