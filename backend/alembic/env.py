import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine
from alembic import context

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# **CRITICAL: Load environment variables BEFORE importing config**
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.core.config import get_settings
from app.database import Base
from app.models import base  # noqa: F401 - registers models with Base.metadata
from app.models import phase2  # noqa: F401 - registers Phase 2 models with Base.metadata
from app.models import phase3  # noqa: F401 - registers Phase 3 models with Base.metadata
from app.models import phase4  # noqa: F401 - registers Phase 4 models with Base.metadata

settings = get_settings()

# Configure the target metadata
target_metadata = Base.metadata

# Interpret the config file for Python logging
# fileConfig("alembic.ini")

# Build the database URL explicitly from environment variables (DB_HOST,
# DB_PORT, DB_NAME, DB_USER, DB_PASSWORD) so each isolated dev/test
# environment is addressed exactly. Never fall back to a stale alembic.ini
# URL; this prevents a migration meant for the test DB from silently
# hitting the dev DB.
config = context.config

# The URL to use: prefer the environment-variable-driven settings object.
settings_url = (
    f"postgresql+psycopg2://{settings.db_user}:{settings.db_password}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
)
config.set_main_option("sqlalchemy.url", settings_url)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "postgresql"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the explicitly configured URL."""
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()
        connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

