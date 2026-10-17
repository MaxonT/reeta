"""Oracle Autonomous Database repository via python-oracledb. STUB, not wired yet.

TODO(oracle):
  1. pip install oracledb
  2. pool = oracledb.create_pool(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN,
         config_dir=ORACLE_WALLET_DIR, wallet_location=ORACLE_WALLET_DIR, wallet_password=...)
  3. Port repo/schema.sql: INTEGER PRIMARY KEY AUTOINCREMENT -> NUMBER GENERATED ALWAYS AS IDENTITY,
     TEXT -> VARCHAR2 / CLOB, JSON columns -> JSON type (23ai) or CLOB with IS JSON check,
     INSERT OR REPLACE -> MERGE, lastrowid -> RETURNING id INTO :out.
  4. Implement every Repository method with the same return shapes as SQLiteRepository
     (tests in backend/tests can be pointed at it to check parity).
"""
from .base import Repository


def _todo(*_a, **_k):
    raise NotImplementedError("OracleRepository is a stub. See TODO in repo/oracle_repo.py")


class OracleRepository(Repository):
    seed_content = list_edges = create_lecture = update_lecture = get_lecture = list_lectures = _todo
    add_sentences = add_entries = list_entries = update_entry = _todo
    list_questions = create_attempt = add_answers = list_attempts = reset_session = _todo
