import inspect

from app.repo.base import Repository
from app.repo.oracle_repo import OracleRepository


def test_oracle_repository_implements_the_interface():
    # Needs no database: importing catches merge leftovers, and no abstract method may be left open.
    assert issubclass(OracleRepository, Repository)
    assert not OracleRepository.__abstractmethods__


def test_oracle_methods_match_the_interface():
    # Same parameters as Repository, so main.py can call either backend the same way.
    for name in Repository.__abstractmethods__:
        want = list(inspect.signature(getattr(Repository, name)).parameters)
        got = list(inspect.signature(getattr(OracleRepository, name)).parameters)
        assert got == want, name
