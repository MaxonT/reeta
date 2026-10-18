"""Postgres repository via asyncpg. The schema is owned by Alembic: run `alembic upgrade head` in backend/.

The service layer is synchronous (FastAPI runs it in the threadpool), so the asyncpg pool lives on its own
event loop in a background thread and each method waits for its query there.
"""
import asyncio
import json
import threading
from datetime import datetime

import asyncpg

from ..config import settings
from .base import Repository
from .pg_url import split_url

_LECTURE_FIELDS = {"audio_path", "text", "words"}
_TOPIC_FIELDS = {"title", "instructions", "questions_per_quiz"}
_USER_COLS = "id, email, name, role, created_at"  # everything but password_hash


def _clean(row) -> dict:
    """Timestamps come back as the same 'YYYY-MM-DD HH:MM:SS' text SQLite gives."""
    row = dict(row)
    for k, v in row.items():
        if isinstance(v, datetime):
            row[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return row


def _count(status: str) -> int:
    """Rows affected, from a status like 'DELETE 1' or 'INSERT 0 1'."""
    return int(status.rsplit(" ", 1)[-1])


def _set_cols(fields: dict, start: int = 1) -> str:
    return ", ".join(f"{k}=${i}" for i, k in enumerate(fields, start))


async def _init_conn(conn):
    # jsonb columns (lectures.words, exam_questions.options) read and write as Python lists
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


class PostgresRepository(Repository):
    def __init__(self, url: str | None = None):
        dsn, ssl = split_url(url or settings.database_url)
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name="postgres-loop", daemon=True).start()
        # statement cache off so it also works through a transaction-mode pooler (Neon's -pooler host)
        async def make_pool():  # create_pool returns an awaitable Pool, run_coroutine_threadsafe wants a coroutine
            return await asyncpg.create_pool(dsn, ssl=ssl, min_size=1, max_size=5,
                                             statement_cache_size=0, init=_init_conn)
        self.pool = self._run(make_pool())
        if not self._run(self.pool.fetchval("SELECT to_regclass('public.alembic_version')")):
            raise RuntimeError("Postgres schema is missing: run `alembic upgrade head` in backend/")

    # helpers
    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def _q(self, sql: str, *args) -> list[dict]:
        return [_clean(r) for r in self._run(self.pool.fetch(sql, *args))]

    def _one(self, sql: str, *args) -> dict | None:
        rows = self._q(sql, *args)
        return rows[0] if rows else None

    def _val(self, sql: str, *args):
        return self._run(self.pool.fetchval(sql, *args))

    def _x(self, sql: str, *args) -> int:
        """Run a write. Returns rows affected."""
        return _count(self._run(self.pool.execute(sql, *args)))

    def _tx(self, fn):
        """Run `async fn(conn)` in one transaction."""
        async def go():
            async with self.pool.acquire() as conn, conn.transaction():
                return await fn(conn)
        return self._run(go())

    def seed_content(self, questions):
        rows = [(q["id"], q["type"], q["prompt"], q["options"], q["correct_answer"]) for q in questions]
        self._run(self.pool.executemany(
            "INSERT INTO exam_questions (id, type, prompt, options, correct_answer) VALUES ($1,$2,$3,$4,$5) "
            "ON CONFLICT (id) DO UPDATE SET type=EXCLUDED.type, prompt=EXCLUDED.prompt, "
            "options=EXCLUDED.options, correct_answer=EXCLUDED.correct_answer", rows))

    # Lectures
    def create_lecture(self, session_id, kind, text):
        return self._val("INSERT INTO lectures (session_id, kind, text) VALUES ($1,$2,$3) RETURNING id",
                         session_id, kind, text)

    def update_lecture(self, lecture_id, **fields):
        bad = set(fields) - _LECTURE_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if fields:
            self._x(f"UPDATE lectures SET {_set_cols(fields, 2)} WHERE id=$1", lecture_id, *fields.values())

    def get_lecture(self, lecture_id):
        return self._one("SELECT * FROM lectures WHERE id=$1", lecture_id)

    def list_lectures(self, session_id):
        return self._q("SELECT * FROM lectures WHERE session_id=$1 ORDER BY id", session_id)

    # Sources
    def add_source(self, session_id, filename, text):
        return self._val("INSERT INTO sources (session_id, filename, text) VALUES ($1,$2,$3) RETURNING id",
                         session_id, filename, text)

    def list_sources(self, session_id):
        return self._q("SELECT * FROM sources WHERE session_id=$1 ORDER BY id", session_id)

    def delete_source(self, session_id, source_id):
        return self._x("DELETE FROM sources WHERE id=$1 AND session_id=$2", source_id, session_id) > 0

    # Exam
    def list_questions(self):
        # q1, q2, ... q10 in number order, like SQLite's CAST(SUBSTR(id, 2) AS INTEGER)
        return self._q("SELECT * FROM exam_questions "
                       "ORDER BY COALESCE(substring(id from '^.(\\d+)')::int, 0), id")

    def create_attempt(self, session_id):
        async def go(c):
            # serialise attempts per session so two runs never get the same attempt_no
            await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", session_id)
            n = await c.fetchval("SELECT COUNT(*) FROM exam_attempts WHERE session_id=$1", session_id)
            aid = await c.fetchval("INSERT INTO exam_attempts (session_id, attempt_no) VALUES ($1,$2) RETURNING id",
                                   session_id, n + 1)
            return aid, n + 1
        return self._tx(go)

    def set_attempt_score(self, attempt_id, score):
        self._x("UPDATE exam_attempts SET score=$1 WHERE id=$2", score, attempt_id)

    def add_answers(self, attempt_id, answers):
        rows = [(attempt_id, a["question_id"], a.get("prompt", ""), a.get("reference_answer", ""),
                 a["answer"], bool(a["is_correct"]), a["reason"], a.get("feedback"),
                 a.get("lecture_id"), a.get("quote"), a.get("quote_start_ms"), a.get("quote_end_ms"),
                 a.get("line")) for a in answers]
        self._run(self.pool.executemany(
            "INSERT INTO exam_answers (attempt_id, question_id, prompt, reference_answer, answer, is_correct, "
            "reason, feedback, lecture_id, quote, quote_start_ms, quote_end_ms, line) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)", rows))

    def list_attempts(self, session_id):
        attempts = self._q("SELECT * FROM exam_attempts WHERE session_id=$1 ORDER BY attempt_no", session_id)
        answers = self._q("SELECT a.* FROM exam_answers a JOIN exam_attempts t ON t.id = a.attempt_id "
                          "WHERE t.session_id=$1 ORDER BY a.attempt_id, a.question_id", session_id)
        for at in attempts:
            at["answers"] = [a for a in answers if a["attempt_id"] == at["id"]]
        return attempts

    def reset_session(self, session_id):
        async def go(c):
            await c.execute("DELETE FROM exam_answers WHERE attempt_id IN "
                            "(SELECT id FROM exam_attempts WHERE session_id=$1)", session_id)
            for table in ("exam_attempts", "lectures", "sources"):
                await c.execute(f"DELETE FROM {table} WHERE session_id=$1", session_id)
        self._tx(go)

    # Accounts
    def _insert_unique(self, sql: str, *args) -> int | None:
        try:
            return self._val(sql, *args)
        except asyncpg.UniqueViolationError:
            return None

    def create_user(self, email, name, role, password_hash):
        return self._insert_unique("INSERT INTO users (email, name, role, password_hash) VALUES ($1,$2,$3,$4) "
                                   "RETURNING id", email, name, role, password_hash)

    def get_user(self, user_id):
        return self._one(f"SELECT {_USER_COLS} FROM users WHERE id=$1", user_id)

    def get_user_by_email(self, email):
        return self._one("SELECT * FROM users WHERE email=$1", email)

    def create_token(self, token_hash, user_id, expires_at):
        self._x("INSERT INTO auth_tokens (token_hash, user_id, expires_at) VALUES ($1,$2,$3)",
                token_hash, user_id, expires_at)

    def user_for_token(self, token_hash, now):
        return self._one(f"SELECT {_USER_COLS} FROM users WHERE id = "
                         "(SELECT user_id FROM auth_tokens WHERE token_hash=$1 AND expires_at > $2)", token_hash, now)

    def delete_token(self, token_hash):
        self._x("DELETE FROM auth_tokens WHERE token_hash=$1", token_hash)

    # Classes
    def create_class(self, teacher_id, name, join_code):
        return self._insert_unique("INSERT INTO classes (teacher_id, name, join_code) VALUES ($1,$2,$3) RETURNING id",
                                   teacher_id, name, join_code)

    def get_class(self, class_id):
        return self._one("SELECT * FROM classes WHERE id=$1", class_id)

    def class_by_code(self, join_code):
        return self._one("SELECT * FROM classes WHERE join_code=$1", join_code)

    def list_teacher_classes(self, teacher_id):
        return self._q("SELECT c.*, (SELECT COUNT(*) FROM class_members m WHERE m.class_id = c.id) AS student_count "
                       "FROM classes c WHERE c.teacher_id=$1 ORDER BY c.id", teacher_id)

    def list_student_classes(self, student_id):
        return self._q("SELECT c.*, u.name AS teacher_name FROM class_members m JOIN classes c ON c.id = m.class_id "
                       "JOIN users u ON u.id = c.teacher_id WHERE m.student_id=$1 ORDER BY m.joined_at, c.id",
                       student_id)

    def add_member(self, class_id, student_id):
        return self._x("INSERT INTO class_members (class_id, student_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                       class_id, student_id) > 0

    def list_members(self, class_id):
        cols = ", ".join(f"u.{c.strip()}" for c in _USER_COLS.split(","))
        return self._q(f"SELECT {cols}, m.joined_at FROM class_members m JOIN users u ON u.id = m.student_id "
                       "WHERE m.class_id=$1 ORDER BY u.name, u.id", class_id)

    def is_member(self, class_id, student_id):
        return bool(self._val("SELECT 1 FROM class_members WHERE class_id=$1 AND student_id=$2", class_id, student_id))

    # Topics
    def create_topic(self, class_id, title, instructions, questions_per_quiz):
        return self._val("INSERT INTO topics (class_id, title, instructions, questions_per_quiz) "
                         "VALUES ($1,$2,$3,$4) RETURNING id", class_id, title, instructions, questions_per_quiz)

    def get_topic(self, topic_id):
        return self._one("SELECT * FROM topics WHERE id=$1", topic_id)

    def list_topics(self, class_id):
        return self._q("SELECT * FROM topics WHERE class_id=$1 ORDER BY id", class_id)

    def update_topic(self, topic_id, **fields):
        bad = set(fields) - _TOPIC_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if fields:
            self._x(f"UPDATE topics SET {_set_cols(fields, 2)} WHERE id=$1", topic_id, *fields.values())
