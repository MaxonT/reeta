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
# Oracle stores '' as NULL, so empty text is written as a single space and mapped back on read.
_EMPTY = " "
_TEXT_COLS = ("text", "prompt", "reference_answer")


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
            min=1, max=4, increment=1)
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

    def seed_content(self, concepts, questions, edges=None):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            for c in concepts:
                cur.execute(
                    "MERGE INTO concepts t USING (SELECT :1 i, :2 l, :3 d FROM dual) s ON (t.id = s.i) "
                    "WHEN MATCHED THEN UPDATE SET t.label=s.l, t.description=s.d "
                    "WHEN NOT MATCHED THEN INSERT (id, label, description) VALUES (s.i, s.l, s.d)",
                    [c["id"], c["label"], c["description"]])
                for m in c.get("misconceptions", []):
                    cur.execute(
                        "MERGE INTO misconceptions t USING (SELECT :1 i, :2 c, :3 d FROM dual) s ON (t.id = s.i) "
                        "WHEN MATCHED THEN UPDATE SET t.concept_id=s.c, t.description=s.d "
                        "WHEN NOT MATCHED THEN INSERT (id, concept_id, description) VALUES (s.i, s.c, s.d)",
                        [m["id"], c["id"], m["description"]])
            if edges is not None:
                cur.execute("DELETE FROM concept_edges")
                for s, t in edges:
                    cur.execute("INSERT INTO concept_edges (source_id, target_id) VALUES (:1,:2)", [s, t])
            for q in questions:
                cur.execute(
                    "MERGE INTO exam_questions t "
                    "USING (SELECT :1 i, :2 ty, :3 p, :4 o, :5 c FROM dual) s ON (t.id = s.i) "
                    "WHEN MATCHED THEN UPDATE SET t.type=s.ty, t.prompt=s.p, t.options=s.o, t.correct_answer=s.c "
                    "WHEN NOT MATCHED THEN INSERT (id, type, prompt, options, correct_answer) "
                    "VALUES (s.i, s.ty, s.p, s.o, s.c)",
                    [q["id"], q["type"], q["prompt"], json.dumps(q["options"]), q["correct_answer"]])
            conn.commit()

    def list_edges(self):
        return [(r["source_id"], r["target_id"])
                for r in self._q("SELECT source_id, target_id FROM concept_edges ORDER BY ROWID")]

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
        return {**row, "words": json.loads(row["words"])}

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

    # Daily loop
    def add_round(self, session_id, created_at, lecture_id, score, total, passed, concept_ids):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            rid = self._insert(
                cur,
                "INSERT INTO loop_rounds (session_id, created_at, lecture_id, score, total, passed, concept_ids) "
                "VALUES (:1,:2,:3,:4,:5,:6,:7)",
                [session_id, created_at, lecture_id, score, total, int(bool(passed)), json.dumps(list(concept_ids))])
            conn.commit()
            return rid

    def list_rounds(self, session_id):
        rows = self._q("SELECT * FROM loop_rounds WHERE session_id=:1 ORDER BY id", (session_id,))
        for r in rows:
            r["passed"] = bool(r["passed"])
            r["concept_ids"] = json.loads(r["concept_ids"])
        return rows

    def reset_session(self, session_id):
        with self.pool.acquire() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM loop_rounds WHERE session_id=:1", [session_id])
            cur.execute("DELETE FROM exam_answers WHERE attempt_id IN "
                        "(SELECT id FROM exam_attempts WHERE session_id=:1)", [session_id])
            cur.execute("DELETE FROM exam_attempts WHERE session_id=:1", [session_id])
            cur.execute("DELETE FROM lectures WHERE session_id=:1", [session_id])
            cur.execute("DELETE FROM sources WHERE session_id=:1", [session_id])
            conn.commit()
