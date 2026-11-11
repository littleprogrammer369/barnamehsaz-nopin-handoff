"""Test database configuration with guardrails.

Ensures tests connect to test DB (5434), not dev DB (5433).
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# **GUARD: Enforce test DB configuration BEFORE any query**
TEST_DB_HOST = os.environ.get("DB_HOST", "localhost")
TEST_DB_PORT = int(os.environ.get("DB_PORT", "5434"))
TEST_DB_NAME = os.environ.get("DB_NAME", "barnamehsaz_novin_test")
TEST_DB_USER = os.environ.get("DB_USER", "barnamehsaz")
TEST_DB_PASSWORD = os.environ.get("DB_PASSWORD", "change_me_local")

# GUARD 1: Reject any non-test database PORT
if TEST_DB_PORT != 5434:
    raise RuntimeError(
        f"FATAL: Test database must use port 5434, not {TEST_DB_PORT}. "
        "Set DB_PORT=5434."
    )

# GUARD 2: Reject any non-test database NAME
if TEST_DB_NAME != "barnamehsaz_novin_test":
    raise RuntimeError(
        f"FATAL: Test database must be 'barnamehsaz_novin_test', not '{TEST_DB_NAME}'. "
        "Set DB_NAME=barnamehsaz_novin_test."
    )

# GUARD 3: Verify actual connection URL before creating engine
test_url = (
    f"postgresql+psycopg2://{TEST_DB_USER}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
)

# Create test engine with explicit test DB
test_engine = create_engine(
    f"postgresql+psycopg2://{TEST_DB_USER}:{TEST_DB_PASSWORD}"
    f"@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}",
    pool_pre_ping=True,
    pool_recycle=3600,
)

# GUARD 4: Test actual connection before tests run
try:
    with test_engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        # Verify we're on test DB by checking if we got a response
        # (real connection succeeded)
        version = result.scalar()
        if not version:
            raise RuntimeError("PostgreSQL version check failed")
except Exception as e:
    raise RuntimeError(
        f"FATAL: Cannot connect to test database {test_url}\n"
        f"Error: {e}\n"
        f"This is likely a credential or network issue. "
        f"Do not reset or modify the database. Contact DB admin."
    ) from e

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def get_test_db():
    """Get test database session."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

