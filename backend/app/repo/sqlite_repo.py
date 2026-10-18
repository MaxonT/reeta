import json
import sqlite3
import threading
from pathlib import Path

from .base import Repository

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
_ENTRY_FIELDS = {"concept_id", "status", "misconception_id", "confirmed", "superseded_by"}


class SQLiteRepository(Repository):
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self._check_schema(path)
            self.conn.executescript(_SCHEMA)

    def _check_schema(self, path):
        # A database created by the reverted open-ended exam (PR #8) has different tables.
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(exam_questions)")]
        if cols and "distractor_map" not in cols:
            raise RuntimeError(f"{path} was created by an older schema (PR #8). Delete it and restart.")

    def _q(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def _x(self, sql: str, args=()) -> int:
        with self.lock, self.conn:
            return self.conn.execute(sql, args).lastrowid

    def seed_content(self, concepts, questions, edges=None):
        with self.lock, self.conn:
            for c in concepts:
                self.conn.execute("INSERT OR REPLACE INTO concepts VALUES (?,?,?)",
                                  (c["id"], c["label"], c["description"]))
                for m in c.get("misconceptions", []):
                    self.conn.execute("INSERT OR REPLACE INTO misconceptions VALUES (?,?,?)",
                                      (m["id"], c["id"], m["description"]))
            if edges is not None:
                self.conn.execute("DELETE FROM concept_edges")
                for s, t in edges:
                    self.conn.execute("INSERT OR IGNORE INTO concept_edges VALUES (?,?)", (s, t))
            for q in questions:
                self.conn.execute(
                    "INSERT OR REPLACE INTO exam_questions VALUES (?,?,?,?,?,?,?)",
                    (q["id"], q["type"], q["prompt"], json.dumps(q["options"]), q["correct_answer"],
                     json.dumps(q["required_concepts"]), json.dumps(q.get("distractor_map", {}))))

    def list_edges(self):
        return [(r["source_id"], r["target_id"]) for r in self._q("SELECT * FROM concept_edges ORDER BY rowid")]

    # Lectures
    def create_lecture(self, session_id, kind, text):
        return self._x("INSERT INTO lectures (session_id, kind, text) VALUES (?,?,?)", (session_id, kind, text))

    def update_lecture(self, lecture_id, **fields):
        bad = set(fields) - {"audio_path", "text"}
        if bad:
            raise ValueError(f"cannot update {bad}")
        if fields:
            cols = ", ".join(f"{k}=?" for k in fields)
            self._x(f"UPDATE lectures SET {cols} WHERE id=?", (*fields.values(), lecture_id))

    def get_lecture(self, lecture_id):
        rows = self._q("SELECT * FROM lectures WHERE id=?", (lecture_id,))
        return rows[0] if rows else None

    def list_lectures(self, session_id):
        lectures = self._q("SELECT * FROM lectures WHERE session_id=? ORDER BY id", (session_id,))
        for lec in lectures:
            lec["sentences"] = self._q("SELECT * FROM sentences WHERE lecture_id=? ORDER BY idx", (lec["id"],))
        return lectures

    def add_sentences(self, lecture_id, sentences):
        out = []
        for s in sentences:
            sid = self._x("INSERT INTO sentences (lecture_id, idx, text, start_ms, end_ms) VALUES (?,?,?,?,?)",
                          (lecture_id, s["idx"], s["text"], s["start_ms"], s["end_ms"]))
            out.append({**s, "id": sid, "lecture_id": lecture_id})
        return out

    # Notebook
    def add_entries(self, session_id, entries):
        out = []
        for e in entries:
            eid = self._x(
                "INSERT INTO notebook_entries (session_id, concept_id, status, misconception_id, sentence_id) "
                "VALUES (?,?,?,?,?)",
                (session_id, e["concept_id"], e["status"], e.get("misconception_id"), e["sentence_id"]))
            out.append({**e, "id": eid, "session_id": session_id, "confirmed": 0, "superseded_by": None})
        return out

    def list_entries(self, session_id, confirmed_only=False):
        sql = ("SELECT e.*, s.lecture_id, s.idx, s.text, s.start_ms, s.end_ms FROM notebook_entries e "
               "JOIN sentences s ON s.id = e.sentence_id WHERE e.session_id=?")
        if confirmed_only:
            sql += " AND e.confirmed=1"
        rows = self._q(sql + " ORDER BY e.id", (session_id,))
        out = []
        for r in rows:
            sentence = {"id": r["sentence_id"], "lecture_id": r.pop("lecture_id"), "idx": r.pop("idx"),
                        "text": r.pop("text"), "start_ms": r.pop("start_ms"), "end_ms": r.pop("end_ms")}
            out.append({**r, "confirmed": bool(r["confirmed"]), "sentence": sentence})
        return out

    def update_entry(self, entry_id, **fields):
        bad = set(fields) - _ENTRY_FIELDS
        if bad:
            raise ValueError(f"cannot update {bad}")
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self._x(f"UPDATE notebook_entries SET {cols} WHERE id=?", (*fields.values(), entry_id))

    # Exam
    def list_questions(self):
        rows = self._q("SELECT * FROM exam_questions ORDER BY CAST(SUBSTR(id, 2) AS INTEGER), id")
        for r in rows:
            for k in ("options", "required_concepts", "distractor_map"):
                r[k] = json.loads(r[k])
        return rows

    def create_attempt(self, session_id, score):
        with self.lock, self.conn:
            n = self.conn.execute("SELECT COUNT(*) FROM exam_attempts WHERE session_id=?", (session_id,)).fetchone()[0]
            aid = self.conn.execute("INSERT INTO exam_attempts (session_id, attempt_no, score) VALUES (?,?,?)",
                                    (session_id, n + 1, score)).lastrowid
        return aid, n + 1

    def add_answers(self, attempt_id, answers):
        with self.lock, self.conn:
            for a in answers:
                self.conn.execute(
                    "INSERT INTO exam_answers VALUES (?,?,?,?,?,?,?,?)",
                    (attempt_id, a["question_id"], a["answer"], int(a["is_correct"]), a["reason"],
                     json.dumps(a["concept_ids"]), json.dumps(a["sentence_ids"]), a.get("line")))

    def list_attempts(self, session_id):
        attempts = self._q("SELECT * FROM exam_attempts WHERE session_id=? ORDER BY attempt_no", (session_id,))
        for at in attempts:
            answers = self._q("SELECT * FROM exam_answers WHERE attempt_id=?", (at["id"],))
            for a in answers:
                a["is_correct"] = bool(a["is_correct"])
                a["concept_ids"] = json.loads(a["concept_ids"])
                a["sentence_ids"] = json.loads(a["sentence_ids"])
            at["answers"] = answers
        return attempts

    # Daily loop
    def add_round(self, session_id, created_at, lecture_id, score, total, passed, concept_ids):
        return self._x(
            "INSERT INTO loop_rounds (session_id, created_at, lecture_id, score, total, passed, concept_ids) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, created_at, lecture_id, score, total, int(bool(passed)), json.dumps(list(concept_ids))))

    def list_rounds(self, session_id):
        rows = self._q("SELECT * FROM loop_rounds WHERE session_id=? ORDER BY id", (session_id,))
        for r in rows:
            r["passed"] = bool(r["passed"])
            r["concept_ids"] = json.loads(r["concept_ids"])
        return rows

    def reset_session(self, session_id):
        with self.lock, self.conn:
            c = self.conn
            c.execute("DELETE FROM loop_rounds WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM exam_answers WHERE attempt_id IN (SELECT id FROM exam_attempts WHERE session_id=?)",
                      (session_id,))
            c.execute("DELETE FROM exam_attempts WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM notebook_entries WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM sentences WHERE lecture_id IN (SELECT id FROM lectures WHERE session_id=?)",
                      (session_id,))
            c.execute("DELETE FROM lectures WHERE session_id=?", (session_id,))
