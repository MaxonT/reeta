"""Oracle Autonomous Database repository via python-oracledb (thin mode, wallet / mTLS)."""
import json
from datetime import datetime
from pathlib import Path

import oracledb

from ..config import _path, settings
from .base import Repository

oracledb.defaults.fetch_lobs = False  # CLOBs come back as plain str

_SCHEMA = (Path(__file__).parent / "oracle_schema.sql").read_text()
_LECTURE_FIELDS = {"audio_path", "text", "words"}
_TOPIC_FIELDS = {"title", "instructions", "questions_per_quiz"}
_USER_COLS = "id, email, name, role, created_at"  # everything but password_hash
# Oracle stores '' as NULL, so empty text is written as a single space and mapped back on read.
_EMPTY = " "
_TEXT_COLS = ("text", "prompt", "reference_answer", "instructions")


def _clean(row: dict) -> dict:
    for k, v in row.items():
        if isinstance(v, datetime):
            row[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, float) and v.is_integer():
            row[k] = int(v)
    for k in _TEXT_COLS:
        if k in row and (row[k] is None or row[k] == _EMPTY):
            row[k] = ""
    return row



class OracleRepository(Repository):
    def __init__(self):
        wallet = str(_path(settings.oracle_wallet_dir))
        self.pool = oracledb.create_pool(
            user=settings.oracle_user, password=settings.oracle_password, dsn=settings.oracle_dsn,
            config_dir=wallet, wallet_location=wallet,
            wallet_password=settings.oracle_wallet_password or None,
            min=1, max=4, increment=1,
            ping_interval=0,  # validate on every acquire so a connection dropped while idle is replaced
            expire_time=1)    # keepalive probe every minute to stop idle drops
        with self.pool.acquire() as conn, conn.cursor() as cur:
            for stmt in _SCHEMA.split("\n/\n"):
                stmt = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
                if not stmt:
                    continue
                try:
                    cur.execute(stmt)
                except oracledb.DatabaseError as e:
                    if "ORA-00955" not in str(e):  # name already used = table exists
                        raise

    # helpers
    def _q(self, sql: str, args=()) -> list[dict]:
        with self.pool.acquire() as conn, conn.cursor() as cur:
            cur.execute(sql, list(args))
            cols = [c[0].lower() for c in cur.description]
            return [_clean(dict(zip(cols, r))) for r in cur.fetchall()]

    def _x(self, sql: str, args=()) -> int:
        """Run a write and commit. Returns rows affected."""
        with self.pool.acquire() as conn, conn.cursor() as cur:
            cur.execute(sql, list(args))
            conn.commit()
            return cur.rowcount

    @staticmethod
    def _insert(cur, sql: str, args) -> int:
        """INSERT ... RETURNING id, for tables with an identity id."""
        out = cur.var(int)
        marks = len(args) + 1
        cur.execute(f"{sql} RETURNING id INTO :{marks}", [*args, out])
        return int(out.getvalue()[0])

    def seed_content(self, questions):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            for q in questions:
                cur.execute(
                    "MERGE INTO exam_questions t "
                    "USING (SELECT :1 i, :2 ty, :3 p, :4 o, :5 c FROM dual) s ON (t.id = s.i) "
                    "WHEN MATCHED THEN UPDATE SET t.type=s.ty, t.prompt=s.p, t.options=s.o, t.correct_answer=s.c "
                    "WHEN NOT MATCHED THEN INSERT (id, type, prompt, options, correct_answer) "
                    "VALUES (s.i, s.ty, s.p, s.o, s.c)",
                    [q["id"], q["type"], q["prompt"], json.dumps(q["options"]), q["correct_answer"]])
            conn.commit()

    # Lectures
    def create_lecture(self, session_id, kind, text):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            lid = self._insert(cur, "INSERT INTO lectures (session_id, kind, text) VALUES (:1,:2,:3)",
                               [session_id, kind, text or _EMPTY])
            conn.commit()
            return lid

    def update_lecture(self, lecture_id, **fields):
        bad = set(fields) - _LECTURE_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if "words" in fields:
            fields["words"] = json.dumps(fields["words"])
        if "text" in fields:
            fields["text"] = fields["text"] or _EMPTY
        if fields:
            cols = ", ".join(f"{k}=:{i}" for i, k in enumerate(fields, 1))
            self._x(f"UPDATE lectures SET {cols} WHERE id=:{len(fields) + 1}", (*fields.values(), lecture_id))

    @staticmethod
    def _lecture(row: dict) -> dict:
        words = row["words"]  # IS JSON columns may already arrive parsed
        return {**row, "words": json.loads(words) if isinstance(words, (str, bytes, bytearray)) else words}

    def get_lecture(self, lecture_id):
        rows = self._q("SELECT * FROM lectures WHERE id=:1", (lecture_id,))
        return self._lecture(rows[0]) if rows else None

    def list_lectures(self, session_id):
        return [self._lecture(r) for r in self._q("SELECT * FROM lectures WHERE session_id=:1 ORDER BY id", (session_id,))]

    # Sources
    def add_source(self, session_id, filename, text):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            sid = self._insert(cur, "INSERT INTO sources (session_id, filename, text) VALUES (:1,:2,:3)",
                               [session_id, filename, text or _EMPTY])
            conn.commit()
            return sid

    def list_sources(self, session_id):
        return self._q("SELECT * FROM sources WHERE session_id=:1 ORDER BY id", (session_id,))

    def delete_source(self, session_id, source_id):
        return self._x("DELETE FROM sources WHERE id=:1 AND session_id=:2", (source_id, session_id)) > 0

    # Exam
    def list_questions(self):
        rows = self._q("SELECT * FROM exam_questions ORDER BY TO_NUMBER(REGEXP_SUBSTR(id, '[0-9]+')), id")
        for r in rows:
            r["options"] = json.loads(r["options"])
        return rows

    def create_attempt(self, session_id):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM exam_attempts WHERE session_id=:1", [session_id])
            n = int(cur.fetchone()[0])
            aid = self._insert(cur, "INSERT INTO exam_attempts (session_id, attempt_no) VALUES (:1,:2)",
                               [session_id, n + 1])
            conn.commit()
        return aid, n + 1

    def set_attempt_score(self, attempt_id, score):
        self._x("UPDATE exam_attempts SET score=:1 WHERE id=:2", (score, attempt_id))

    def add_answers(self, attempt_id, answers):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            for a in answers:
                cur.execute(
                    "INSERT INTO exam_answers (attempt_id, question_id, prompt, reference_answer, answer, "
                    "is_correct, reason, feedback, lecture_id, quote, quote_start_ms, quote_end_ms, line) "
                    "VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13)",
                    [attempt_id, a["question_id"], a.get("prompt", "") or _EMPTY,
                     a.get("reference_answer", "") or _EMPTY, a["answer"], int(a["is_correct"]), a["reason"],
                     a.get("feedback"), a.get("lecture_id"), a.get("quote"), a.get("quote_start_ms"),
                     a.get("quote_end_ms"), a.get("line")])
            conn.commit()

    def list_attempts(self, session_id):
        attempts = self._q("SELECT * FROM exam_attempts WHERE session_id=:1 ORDER BY attempt_no", (session_id,))
        for at in attempts:
            answers = self._q("SELECT * FROM exam_answers WHERE attempt_id=:1 ORDER BY question_id", (at["id"],))
            for a in answers:
                a["is_correct"] = bool(a["is_correct"])
            at["answers"] = answers
        return attempts

    def reset_session(self, session_id):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM loop_rounds WHERE session_id=:1", [session_id])
            cur.execute("DELETE FROM exam_answers WHERE attempt_id IN "
                        "(SELECT id FROM exam_attempts WHERE session_id=:1)", [session_id])
            cur.execute("DELETE FROM exam_attempts WHERE session_id=:1", [session_id])
            cur.execute("DELETE FROM lectures WHERE session_id=:1", [session_id])
            cur.execute("DELETE FROM sources WHERE session_id=:1", [session_id])
            conn.commit()

    # Accounts
    def _insert_unique(self, sql: str, args) -> int | None:
        with self.pool.acquire() as conn, conn.cursor() as cur:
            try:
                new_id = self._insert(cur, sql, args)
            except oracledb.IntegrityError:  # ORA-00001 unique constraint
                return None
            conn.commit()
            return new_id

    def create_user(self, email, name, role, password_hash):
        return self._insert_unique("INSERT INTO users (email, name, role, password_hash) VALUES (:1,:2,:3,:4)",
                                   [email, name, role, password_hash])

    def get_user(self, user_id):
        rows = self._q(f"SELECT {_USER_COLS} FROM users WHERE id=:1", (user_id,))
        return rows[0] if rows else None

    def get_user_by_email(self, email):
        rows = self._q("SELECT * FROM users WHERE email=:1", (email,))
        return rows[0] if rows else None

    def create_token(self, token_hash, user_id, expires_at):
        self._x("INSERT INTO auth_tokens (token_hash, user_id, expires_at) VALUES (:1,:2,:3)",
                (token_hash, user_id, expires_at))

    def user_for_token(self, token_hash, now):
        rows = self._q(f"SELECT {_USER_COLS} FROM users WHERE id = "
                       "(SELECT user_id FROM auth_tokens WHERE token_hash=:1 AND expires_at > :2)", (token_hash, now))
        return rows[0] if rows else None

    def delete_token(self, token_hash):
        self._x("DELETE FROM auth_tokens WHERE token_hash=:1", (token_hash,))

    # Classes
    def create_class(self, teacher_id, name, join_code):
        return self._insert_unique("INSERT INTO classes (teacher_id, name, join_code) VALUES (:1,:2,:3)",
                                   [teacher_id, name, join_code])

    def get_class(self, class_id):
        rows = self._q("SELECT * FROM classes WHERE id=:1", (class_id,))
        return rows[0] if rows else None

    def class_by_code(self, join_code):
        rows = self._q("SELECT * FROM classes WHERE join_code=:1", (join_code,))
        return rows[0] if rows else None

    def list_teacher_classes(self, teacher_id):
        return self._q("SELECT c.*, (SELECT COUNT(*) FROM class_members m WHERE m.class_id = c.id) AS student_count "
                       "FROM classes c WHERE c.teacher_id=:1 ORDER BY c.id", (teacher_id,))

    def list_student_classes(self, student_id):
        return self._q("SELECT c.*, u.name AS teacher_name FROM class_members m JOIN classes c ON c.id = m.class_id "
                       "JOIN users u ON u.id = c.teacher_id WHERE m.student_id=:1 ORDER BY m.joined_at, c.id",
                       (student_id,))

    def add_member(self, class_id, student_id):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO class_members (class_id, student_id) VALUES (:1,:2)", [class_id, student_id])
            except oracledb.IntegrityError:  # already a member
                return False
            conn.commit()
            return True

    def list_members(self, class_id):
        cols = ", ".join(f"u.{c.strip()}" for c in _USER_COLS.split(","))
        return self._q(f"SELECT {cols}, m.joined_at FROM class_members m JOIN users u ON u.id = m.student_id "
                       "WHERE m.class_id=:1 ORDER BY u.name, u.id", (class_id,))

    def is_member(self, class_id, student_id):
        return bool(self._q("SELECT 1 FROM class_members WHERE class_id=:1 AND student_id=:2", (class_id, student_id)))

    # Topics
    def create_topic(self, class_id, title, instructions, questions_per_quiz):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            tid = self._insert(cur, "INSERT INTO topics (class_id, title, instructions, questions_per_quiz) "
                                    "VALUES (:1,:2,:3,:4)", [class_id, title, instructions or None, questions_per_quiz])
            conn.commit()
            return tid

    def get_topic(self, topic_id):
        rows = self._q("SELECT * FROM topics WHERE id=:1", (topic_id,))
        return rows[0] if rows else None

    def list_topics(self, class_id):
        return self._q("SELECT * FROM topics WHERE class_id=:1 ORDER BY id", (class_id,))

    def update_topic(self, topic_id, **fields):
        bad = set(fields) - _TOPIC_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if "instructions" in fields:
            fields["instructions"] = fields["instructions"] or None  # Oracle stores '' as NULL anyway
        if fields:
            cols = ", ".join(f"{k}=:{i}" for i, k in enumerate(fields, 1))
            self._x(f"UPDATE topics SET {cols} WHERE id=:{len(fields) + 1}", (*fields.values(), topic_id))
