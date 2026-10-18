import sqlite3

import pytest

from app.repo.sqlite_repo import SQLiteRepository


def test_database_from_reverted_schema_gives_a_clear_error(tmp_path):
    path = tmp_path / "reeta.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE exam_questions (id TEXT PRIMARY KEY, attempt_id INTEGER, prompt TEXT,"
                 " reference_answer TEXT, position INTEGER)")
    conn.close()

    with pytest.raises(RuntimeError, match="Delete it and restart"):
        SQLiteRepository(path)


def test_current_database_is_kept(tmp_path, key, questions):
    path = tmp_path / "reeta.db"
    repo = SQLiteRepository(path)
    repo.seed_content(key.concepts, questions, key.edges)
    lecture_id = repo.create_lecture("s1", "lecture", "hello")
    repo.conn.close()

    again = SQLiteRepository(path)
    again.seed_content(key.concepts, questions, key.edges)
    assert again._q("SELECT id FROM lectures") == [{"id": lecture_id}]
