from app.repo.base import Repository
from app.repo.oracle_repo import OracleRepository


def test_oracle_repository_implements_the_interface():
    # Needs no database: importing catches merge leftovers, and no abstract method may be left open.
    assert issubclass(OracleRepository, Repository)
    assert not OracleRepository.__abstractmethods__
