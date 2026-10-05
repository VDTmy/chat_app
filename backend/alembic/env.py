"""
Alembic env.py — configured for async SQLAlchemy (asyncpg).
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.db.base import Base

# Import all models so that Base.metadata is fully populated
from app.models.user import User  # noqa: F401
from app.models.friendship import Friendship  # noqa: F401
from app.models.conversation import Conversation  # noqa: F401
from app.models.conversation_member import ConversationMember  # noqa: F401
from app.models.message import Message  # noqa: F401

# ── Alembic Config object ──────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from our application settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData for autogenerate support
target_metadata = Base.metadata


# ── Offline migrations ─────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL — no Engine needed.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online (async) migrations ─────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    """Run migrations inside a synchronous connection callback."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async)."""
    asyncio.run(run_async_migrations())


# ── Entrypoint ─────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
