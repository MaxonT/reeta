"""Alembic env: async engine on asyncpg, URL from DATABASE_URL. Migrations are written by hand
(`alembic revision -m "..."`), there are no SQLAlchemy models to autogenerate from."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.repo.pg_url import sqlalchemy_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

URL, CONNECT_ARGS = sqlalchemy_url(settings.database_url)


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    context.configure(url=URL, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(URL, connect_args=CONNECT_ARGS, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
