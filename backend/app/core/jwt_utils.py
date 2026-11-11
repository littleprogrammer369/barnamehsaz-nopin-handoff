import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from app.core.config import get_settings

settings = get_settings()
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"

REFRESH_TOKEN_TTL_DAYS = 7


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token (stateless, short-lived)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, family_id: Optional[str] = None) -> str:
    """Create a JWT refresh token (longer expiry, unique jti + family id)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "family": family_id or str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_refresh_token(token: str) -> str:
    """Return the SHA-256 hex digest of a refresh token.

    Only this digest (never the raw token) is persisted server-side, so a
    DB leak does not expose usable refresh tokens.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_family_id() -> str:
    """A fresh token family (one login = one family)."""
    return str(uuid.uuid4())

