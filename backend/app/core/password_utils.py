from passlib.context import CryptContext

# Configure Argon2 context for password hashing
# Use the modern argon2-cffi bindings for Argon2id support
pwd_context = CryptContext(
    schemes=['argon2'],
    deprecated='auto',
)

# Optional: manually register argon2 handler if not auto-discovered
try:
    from argon2 import PasswordHasher
    from argon2 import Type
    from argon2 import exceptions as argon2_exceptions
    _ph = PasswordHasher()
except ImportError:
    _ph = None


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    if not password:
        raise ValueError("Password cannot be empty")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False
