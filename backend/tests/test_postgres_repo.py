import inspect

import pytest

from app.repo.base import Repository
from app.repo.pg_url import split_url, sqlalchemy_url
from app.repo.postgres_repo import PostgresRepository

NEON = "postgresql://u:p@ep-x-pooler.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


def test_postgres_repository_implements_the_interface():
    assert issubclass(PostgresRepository, Repository)
    assert not PostgresRepository.__abstractmethods__


def test_postgres_methods_match_the_interface():
    for name in Repository.__abstractmethods__:
        want = list(inspect.signature(getattr(Repository, name)).parameters)
        got = list(inspect.signature(getattr(PostgresRepository, name)).parameters)
        assert got == want, name


def test_neon_url_is_split_for_asyncpg():
    assert split_url(NEON) == ("postgresql://u:p@ep-x-pooler.aws.neon.tech/neondb", "require")
    assert split_url("postgres://u@h/db?application_name=reeta") == ("postgresql://u@h/db?application_name=reeta", None)


def test_neon_url_for_alembic():
    url, args = sqlalchemy_url(NEON)
    assert url == "postgresql+asyncpg://u:p@ep-x-pooler.aws.neon.tech/neondb"
    assert args == {"statement_cache_size": 0, "ssl": "require"}


def test_missing_or_wrong_url():
    with pytest.raises(ValueError):
        split_url("")
    with pytest.raises(ValueError):
        split_url("mysql://u@h/db")
