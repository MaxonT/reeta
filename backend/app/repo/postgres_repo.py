"""PostgreSQL repository via asyncpg. The schema is owned by Alembic (backend/migrations).

asyncpg is async only and Repository is sync, so a private event loop runs on a background thread and
every call blocks on it. That works from sync and async FastAPI handlers alike.
"""
import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg

from .base import Repository

BACKEND_DIR = Path(__file__).resolve().parents[2]
_LECTURE_FIELDS = {"audio_path", "text", "words"}
_TOPIC_FIELDS = {"title", "instructions", "questions_per_quiz"}
_USER_COLS = "id, email, name, role, created_at"  # everything but password_hash
_DROP_PARAMS = {"channel_binding"}  # libpq-only option that asyncpg rejects (Neon adds it)


def _split(url: str, scheme: str, ssl_key: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _DROP_PARAMS]
    query = [(ssl_key if k == "sslmode" else k, v) for k, v in query]
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def asyncpg_dsn(url: str) -> str:
    """URL for asyncpg.create_pool (accepts sslmode=)."""
    return _split(url, "postgresql", "sslmode")


def sqlalchemy_url(url: str) -> str:
    """URL for SQLAlchemy's asyncpg dialect, used by Alembic (wants ssl=, not sslmode=)."""
    return _split(url, "postgresql+asyncpg", "ssl")


def _clean(row: dict) -> dict:
    for k, v in row.items():
        if isinstance(v, datetime):
            row[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return row


def migrate(url: str) -> None:
    """alembic upgrade head. Run in its own thread: Alembic's env.py calls asyncio.run."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    err: list[BaseException] = []

    def work():
        try:
            command.upgrade(cfg, "head")
        except BaseException as e:  # re-raised in the caller
            err.append(e)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    if err:
        raise err[0]


class PostgresRepository(Repository):
    def __init__(self, url: str):
        if not url:
            raise ValueError("DB_PROVIDER=postgres needs POSTGRES_URL (or DATABASE_URL) in the env")
        migrate(url)
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True, name="asyncpg-loop").start()

        async def open_pool():  # create_pool returns an awaitable Pool, not a coroutine
            return await asyncpg.create_pool(asyncpg_dsn(url), min_size=1, max_size=4)

        self.pool = self._run(open_pool())

    # helpers
    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def _q(self, sql: str, args=()) -> list[dict]:
        async def go():
            async with self.pool.acquire() as c:
                return [_clean(dict(r)) for r in await c.fetch(sql, *args)]
        return self._run(go())

    def _x(self, sql: str, args=()) -> int:
        """Run a write. Returns rows affected."""
        async def go():
            async with self.pool.acquire() as c:
                return await c.execute(sql, *args)
        status = self._run(go())  # e.g. "DELETE 3", "INSERT 0 1"
        return int(status.rsplit(" ", 1)[-1])

    def _insert(self, sql: str, args) -> int:
        async def go():
            async with self.pool.acquire() as c:
                return await c.fetchval(f"{sql} RETURNING id", *args)
        return int(self._run(go()))

    def _insert_unique(self, sql: str, args) -> int | None:
        try:
            return self._insert(sql, args)
        except asyncpg.UniqueViolationError:
            return None

    def _tx(self, work):
        """work(conn) is a coroutine function; runs inside one transaction."""
        async def go():
            async with self.pool.acquire() as c, c.transaction():
                return await work(c)
        return self._run(go())

    def seed_content(self, questions):
        async def work(c):
            for q in questions:
                await c.execute(
                    "INSERT INTO exam_questions (id, type, prompt, options, correct_answer) VALUES ($1,$2,$3,$4,$5) "
                    "ON CONFLICT (id) DO UPDATE SET type=EXCLUDED.type, prompt=EXCLUDED.prompt, "
                    "options=EXCLUDED.options, correct_answer=EXCLUDED.correct_answer",
                    q["id"], q["type"], q["prompt"], json.dumps(q["options"]), q["correct_answer"])
        self._tx(work)

    # Lectures
    def create_lecture(self, session_id, kind, text):
        return self._insert("INSERT INTO lectures (session_id, kind, text) VALUES ($1,$2,$3)",
                            (session_id, kind, text))

    def update_lecture(self, lecture_id, **fields):
        bad = set(fields) - _LECTURE_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if "words" in fields:
            fields["words"] = json.dumps(fields["words"])
        if fields:
            cols = ", ".join(f"{k}=${i}" for i, k in enumerate(fields, 1))
            self._x(f"UPDATE lectures SET {cols} WHERE id=${len(fields) + 1}", (*fields.values(), lecture_id))

    @staticmethod
    def _lecture(row: dict) -> dict:
        return {**row, "words": json.loads(row["words"])}

    def get_lecture(self, lecture_id):
        rows = self._q("SELECT * FROM lectures WHERE id=$1", (lecture_id,))
        return self._lecture(rows[0]) if rows else None

    def list_lectures(self, session_id):
        return [self._lecture(r) for r in self._q("SELECT * FROM lectures WHERE session_id=$1 ORDER BY id", (session_id,))]

    # Sources
    def add_source(self, session_id, filename, text):
        return self._insert("INSERT INTO sources (session_id, filename, text) VALUES ($1,$2,$3)",
                            (session_id, filename, text))

    def list_sources(self, session_id):
        return self._q("SELECT * FROM sources WHERE session_id=$1 ORDER BY id", (session_id,))

    def delete_source(self, session_id, source_id):
        return self._x("DELETE FROM sources WHERE id=$1 AND session_id=$2", (source_id, session_id)) > 0

    # Exam
    def list_questions(self):
        rows = self._q("SELECT * FROM exam_questions "
                       "ORDER BY NULLIF(regexp_replace(id, '\\D', '', 'g'), '')::int, id")
        for r in rows:
            r["options"] = json.loads(r["options"])
        return rows

    def create_attempt(self, session_id):
        async def work(c):
            n = await c.fetchval("SELECT COUNT(*) FROM exam_attempts WHERE session_id=$1", session_id)
            aid = await c.fetchval("INSERT INTO exam_attempts (session_id, attempt_no) VALUES ($1,$2) RETURNING id",
                                   session_id, n + 1)
            return int(aid), n + 1
        return self._tx(work)

    def set_attempt_score(self, attempt_id, score):
        self._x("UPDATE exam_attempts SET score=$1 WHERE id=$2", (score, attempt_id))

    def add_answers(self, attempt_id, answers):
        async def work(c):
            for a in answers:
                await c.execute(
                    "INSERT INTO exam_answers (attempt_id, question_id, prompt, reference_answer, answer, "
                    "is_correct, reason, feedback, lecture_id, quote, quote_start_ms, quote_end_ms, line) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)",
                    attempt_id, a["question_id"], a.get("prompt", ""), a.get("reference_answer", ""),
                    a["answer"], bool(a["is_correct"]), a["reason"], a.get("feedback"), a.get("lecture_id"),
                    a.get("quote"), a.get("quote_start_ms"), a.get("quote_end_ms"), a.get("line"))
        self._tx(work)

    def list_attempts(self, session_id):
        attempts = self._q("SELECT * FROM exam_attempts WHERE session_id=$1 ORDER BY attempt_no", (session_id,))
        for at in attempts:
            answers = self._q("SELECT * FROM exam_answers WHERE attempt_id=$1 ORDER BY question_id", (at["id"],))
            for a in answers:
                a["is_correct"] = bool(a["is_correct"])
            at["answers"] = answers
        return attempts

    def reset_session(self, session_id):
        async def work(c):
            await c.execute("DELETE FROM exam_answers WHERE attempt_id IN "
                            "(SELECT id FROM exam_attempts WHERE session_id=$1)", session_id)
            await c.execute("DELETE FROM exam_attempts WHERE session_id=$1", session_id)
            await c.execute("DELETE FROM lectures WHERE session_id=$1", session_id)
            await c.execute("DELETE FROM sources WHERE session_id=$1", session_id)
        self._tx(work)

    # Accounts
    def create_user(self, email, name, role, password_hash):
        return self._insert_unique("INSERT INTO users (email, name, role, password_hash) VALUES ($1,$2,$3,$4)",
                                   (email, name, role, password_hash))

    def get_user(self, user_id):
        rows = self._q(f"SELECT {_USER_COLS} FROM users WHERE id=$1", (user_id,))
        return rows[0] if rows else None

    def get_user_by_email(self, email):
        rows = self._q("SELECT * FROM users WHERE email=$1", (email,))
        return rows[0] if rows else None

    def create_token(self, token_hash, user_id, expires_at):
        self._x("INSERT INTO auth_tokens (token_hash, user_id, expires_at) VALUES ($1,$2,$3)",
                (token_hash, user_id, expires_at))

    def user_for_token(self, token_hash, now):
        rows = self._q(f"SELECT {_USER_COLS} FROM users WHERE id = "
                       "(SELECT user_id FROM auth_tokens WHERE token_hash=$1 AND expires_at > $2)", (token_hash, now))
        return rows[0] if rows else None

    def delete_token(self, token_hash):
        self._x("DELETE FROM auth_tokens WHERE token_hash=$1", (token_hash,))

    # Classes
    def create_class(self, teacher_id, name, join_code):
        return self._insert_unique("INSERT INTO classes (teacher_id, name, join_code) VALUES ($1,$2,$3)",
                                   (teacher_id, name, join_code))

    def get_class(self, class_id):
        rows = self._q("SELECT * FROM classes WHERE id=$1", (class_id,))
        return rows[0] if rows else None

    def class_by_code(self, join_code):
        rows = self._q("SELECT * FROM classes WHERE join_code=$1", (join_code,))
        return rows[0] if rows else None

    def list_teacher_classes(self, teacher_id):
        return self._q("SELECT c.*, (SELECT COUNT(*) FROM class_members m WHERE m.class_id = c.id)::int AS student_count "
                       "FROM classes c WHERE c.teacher_id=$1 ORDER BY c.id", (teacher_id,))

    def list_student_classes(self, student_id):
        return self._q("SELECT c.*, u.name AS teacher_name FROM class_members m JOIN classes c ON c.id = m.class_id "
                       "JOIN users u ON u.id = c.teacher_id WHERE m.student_id=$1 ORDER BY m.joined_at, c.id",
                       (student_id,))

    def add_member(self, class_id, student_id):
        return self._x("INSERT INTO class_members (class_id, student_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                       (class_id, student_id)) > 0

    def list_members(self, class_id):
        cols = ", ".join(f"u.{c.strip()}" for c in _USER_COLS.split(","))
        return self._q(f"SELECT {cols}, m.joined_at FROM class_members m JOIN users u ON u.id = m.student_id "
                       "WHERE m.class_id=$1 ORDER BY u.name, u.id", (class_id,))

    def is_member(self, class_id, student_id):
        return bool(self._q("SELECT 1 FROM class_members WHERE class_id=$1 AND student_id=$2", (class_id, student_id)))

    # Topics
    def create_topic(self, class_id, title, instructions, questions_per_quiz):
        return self._insert("INSERT INTO topics (class_id, title, instructions, questions_per_quiz) "
                            "VALUES ($1,$2,$3,$4)", (class_id, title, instructions or "", questions_per_quiz))

    def get_topic(self, topic_id):
        rows = self._q("SELECT * FROM topics WHERE id=$1", (topic_id,))
        return rows[0] if rows else None

    def list_topics(self, class_id):
        return self._q("SELECT * FROM topics WHERE class_id=$1 ORDER BY id", (class_id,))

    def update_topic(self, topic_id, **fields):
        bad = set(fields) - _TOPIC_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if fields:
            cols = ", ".join(f"{k}=${i}" for i, k in enumerate(fields, 1))
            self._x(f"UPDATE topics SET {_set_cols(fields, 2)} WHERE id=$1", topic_id, *fields.values())
