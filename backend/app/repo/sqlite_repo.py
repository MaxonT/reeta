import json
import sqlite3
import threading
from pathlib import Path

from .base import Repository

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
_LECTURE_FIELDS = {"audio_path", "text", "words"}
_TOPIC_FIELDS = {"title", "instructions", "questions_per_quiz"}
_USER_COLS = "id, email, name, role, created_at"  # everything but password_hash


class SQLiteRepository(Repository):
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(_SCHEMA)

    def _q(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def _x(self, sql: str, args=()) -> int:
        with self.lock, self.conn:
            return self.conn.execute(sql, args).lastrowid

    # Lectures
    def create_lecture(self, session_id, kind, text):
        return self._x("INSERT INTO lectures (session_id, kind, text) VALUES (?,?,?)", (session_id, kind, text))

    def update_lecture(self, lecture_id, **fields):
        bad = set(fields) - _LECTURE_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if "words" in fields:
            fields["words"] = json.dumps(fields["words"])
        if fields:
            cols = ", ".join(f"{k}=?" for k in fields)
            self._x(f"UPDATE lectures SET {cols} WHERE id=?", (*fields.values(), lecture_id))

    @staticmethod
    def _lecture(row: dict) -> dict:
        return {**row, "words": json.loads(row["words"])}

    def get_lecture(self, lecture_id):
        rows = self._q("SELECT * FROM lectures WHERE id=?", (lecture_id,))
        return self._lecture(rows[0]) if rows else None

    def list_lectures(self, session_id):
        return [self._lecture(r) for r in self._q("SELECT * FROM lectures WHERE session_id=? ORDER BY id", (session_id,))]

    # Sources
    def add_source(self, session_id, filename, text):
        return self._x("INSERT INTO sources (session_id, filename, text) VALUES (?,?,?)", (session_id, filename, text))

    def list_sources(self, session_id):
        return self._q("SELECT * FROM sources WHERE session_id=? ORDER BY id", (session_id,))

    def delete_source(self, session_id, source_id):
        with self.lock, self.conn:
            cur = self.conn.execute("DELETE FROM sources WHERE id=? AND session_id=?", (source_id, session_id))
            return cur.rowcount > 0

    # Exam
    def list_questions(self):
        rows = self._q("SELECT * FROM exam_questions ORDER BY CAST(SUBSTR(id, 2) AS INTEGER), id")
        for r in rows:
            r["options"] = json.loads(r["options"])
        return rows

    def create_attempt(self, session_id):
        with self.lock, self.conn:
            n = self.conn.execute("SELECT COUNT(*) FROM exam_attempts WHERE session_id=?", (session_id,)).fetchone()[0]
            aid = self.conn.execute("INSERT INTO exam_attempts (session_id, attempt_no) VALUES (?,?)",
                                    (session_id, n + 1)).lastrowid
        return aid, n + 1

    def set_attempt_score(self, attempt_id, score):
        self._x("UPDATE exam_attempts SET score=? WHERE id=?", (score, attempt_id))

    def add_answers(self, attempt_id, answers):
        with self.lock, self.conn:
            for a in answers:
                self.conn.execute(
                    "INSERT INTO exam_answers (attempt_id, question_id, prompt, reference_answer, answer, "
                    "is_correct, reason, feedback, lecture_id, quote, quote_start_ms, quote_end_ms, line) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (attempt_id, a["question_id"], a.get("prompt", ""), a.get("reference_answer", ""),
                     a["answer"], int(a["is_correct"]), a["reason"], a.get("feedback"),
                     a.get("lecture_id"), a.get("quote"), a.get("quote_start_ms"), a.get("quote_end_ms"),
                     a.get("line")))

    def list_attempts(self, session_id):
        attempts = self._q("SELECT * FROM exam_attempts WHERE session_id=? ORDER BY attempt_no", (session_id,))
        for at in attempts:
            answers = self._q("SELECT * FROM exam_answers WHERE attempt_id=? ORDER BY question_id", (at["id"],))
            for a in answers:
                a["is_correct"] = bool(a["is_correct"])
            at["answers"] = answers
        return attempts

    def reset_session(self, session_id):
        with self.lock, self.conn:
            c = self.conn
            c.execute("DELETE FROM exam_answers WHERE attempt_id IN (SELECT id FROM exam_attempts WHERE session_id=?)",
                      (session_id,))
            c.execute("DELETE FROM exam_attempts WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM lectures WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM sources WHERE session_id=?", (session_id,))

    # Accounts
    def _insert_unique(self, sql: str, args) -> int | None:
        try:
            return self._x(sql, args)
        except sqlite3.IntegrityError:
            return None

    def create_user(self, email, name, role, password_hash):
        return self._insert_unique("INSERT INTO users (email, name, role, password_hash) VALUES (?,?,?,?)",
                                   (email, name, role, password_hash))

    def get_user(self, user_id):
        rows = self._q(f"SELECT {_USER_COLS} FROM users WHERE id=?", (user_id,))
        return rows[0] if rows else None

    def get_user_by_email(self, email):
        rows = self._q("SELECT * FROM users WHERE email=?", (email,))
        return rows[0] if rows else None

    def create_token(self, token_hash, user_id, expires_at):
        self._x("INSERT INTO auth_tokens (token_hash, user_id, expires_at) VALUES (?,?,?)",
                (token_hash, user_id, expires_at))

    def user_for_token(self, token_hash, now):
        rows = self._q(f"SELECT {_USER_COLS} FROM users WHERE id = "
                       "(SELECT user_id FROM auth_tokens WHERE token_hash=? AND expires_at > ?)", (token_hash, now))
        return rows[0] if rows else None

    def delete_token(self, token_hash):
        self._x("DELETE FROM auth_tokens WHERE token_hash=?", (token_hash,))

    # Classes
    def create_class(self, teacher_id, name, join_code):
        return self._insert_unique("INSERT INTO classes (teacher_id, name, join_code) VALUES (?,?,?)",
                                   (teacher_id, name, join_code))

    def get_class(self, class_id):
        rows = self._q("SELECT * FROM classes WHERE id=?", (class_id,))
        return rows[0] if rows else None

    def class_by_code(self, join_code):
        rows = self._q("SELECT * FROM classes WHERE join_code=?", (join_code,))
        return rows[0] if rows else None

    def list_teacher_classes(self, teacher_id):
        return self._q("SELECT c.*, (SELECT COUNT(*) FROM class_members m WHERE m.class_id = c.id) AS student_count "
                       "FROM classes c WHERE c.teacher_id=? ORDER BY c.id", (teacher_id,))

    def list_student_classes(self, student_id):
        return self._q("SELECT c.*, u.name AS teacher_name FROM class_members m JOIN classes c ON c.id = m.class_id "
                       "JOIN users u ON u.id = c.teacher_id WHERE m.student_id=? ORDER BY m.joined_at, c.id",
                       (student_id,))

    def add_member(self, class_id, student_id):
        with self.lock, self.conn:
            cur = self.conn.execute("INSERT OR IGNORE INTO class_members (class_id, student_id) VALUES (?,?)",
                                    (class_id, student_id))
            return cur.rowcount > 0

    def list_members(self, class_id):
        cols = ", ".join(f"u.{c.strip()}" for c in _USER_COLS.split(","))
        return self._q(f"SELECT {cols}, m.joined_at FROM class_members m JOIN users u ON u.id = m.student_id "
                       "WHERE m.class_id=? ORDER BY u.name, u.id", (class_id,))

    def is_member(self, class_id, student_id):
        return bool(self._q("SELECT 1 FROM class_members WHERE class_id=? AND student_id=?", (class_id, student_id)))

    # Topics
    def create_topic(self, class_id, title, instructions, questions_per_quiz):
        return self._x("INSERT INTO topics (class_id, title, instructions, questions_per_quiz) VALUES (?,?,?,?)",
                       (class_id, title, instructions, questions_per_quiz))

    def get_topic(self, topic_id):
        rows = self._q("SELECT * FROM topics WHERE id=?", (topic_id,))
        return rows[0] if rows else None

    def list_topics(self, class_id):
        return self._q("SELECT * FROM topics WHERE class_id=? ORDER BY id", (class_id,))

    def update_topic(self, topic_id, **fields):
        bad = set(fields) - _TOPIC_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if fields:
            cols = ", ".join(f"{k}=?" for k in fields)
            self._x(f"UPDATE topics SET {cols} WHERE id=?", (*fields.values(), topic_id))
