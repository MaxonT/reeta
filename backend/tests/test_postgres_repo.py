import inspect

from app.repo.base import Repository
from app.repo.postgres_repo import PostgresRepository, asyncpg_dsn, sqlalchemy_url
import pytest

from app.repo.pg_url import split_url, sqlalchemy_url

NEON = "postgresql://u:p@ep-x-pooler.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


def test_postgres_repository_implements_the_interface():
    assert issubclass(PostgresRepository, Repository)
    assert not PostgresRepository.__abstractmethods__


def test_postgres_methods_match_the_interface():
    for name in Repository.__abstractmethods__:
        want = list(inspect.signature(getattr(Repository, name)).parameters)
        got = list(inspect.signature(getattr(PostgresRepository, name)).parameters)
        assert got == want, name


def test_urls_are_adapted_to_each_driver():
    url = "postgres://u:p@h:5432/db?sslmode=require&channel_binding=require"
    assert asyncpg_dsn(url) == "postgresql://u:p@h:5432/db?sslmode=require"
    assert sqlalchemy_url(url) == "postgresql+asyncpg://u:p@h:5432/db?ssl=require"
