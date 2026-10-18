"""Business logic. Talks only to the SpeechClient / LLMClient / Repository interfaces."""
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from . import persona
from .content import AnswerKey
from .grading import CORRECT, MISCONCEPTION, NOT_TAUGHT, concept_status, grade_exam
from .llm.base import LLMClient, template_phrase
from .repo.base import Repository
from .speech.base import SpeechClient


class ReetaService:
    def __init__(self, repo: Repository, speech: SpeechClient, llm: LLMClient, key: AnswerKey,
                 audio_dir: Path, pass_threshold: float = 1.0, clock: Callable[[], datetime] = datetime.now):
        self.repo, self.speech, self.llm, self.key = repo, speech, llm, key
        self.audio_dir = audio_dir
        self.pass_threshold = pass_threshold
        self.clock = clock  # server local time; injectable so tests can time travel

    # 1-4. Record, transcribe, split, extract
    def ingest_lecture(self, session_id: str, kind: str, audio: bytes | None, audio_ext: str,
                       client_sentences: list[dict] | None, typed_text: str | None) -> dict:
        from .sentences import text_to_sentences

        lecture_id = self.repo.create_lecture(session_id, kind, "")
        audio_path = None
        if audio:
            self.audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = self.audio_dir / f"lecture_{lecture_id}{audio_ext}"
            audio_path.write_bytes(audio)
            self.repo.update_lecture(lecture_id, audio_path=str(audio_path))

        sentences, source, warning = [], None, None
        if audio_path is not None:
            try:
                sentences, source = self.speech.transcribe(audio_path), "server"
            except NotImplementedError:
                pass
            except Exception as exc:  # noqa: BLE001 fall back to the browser transcript
                warning = f"Server transcription failed ({exc.__class__.__name__}); used browser transcript."
        if not sentences and client_sentences:
            sentences, source = _clean_client_sentences(client_sentences), "browser"
        if not sentences and typed_text:
            sentences, source = text_to_sentences(typed_text), "typed"

        text = " ".join(s["text"] for s in sentences)
        self.repo.update_lecture(lecture_id, text=text)
        stored = self.repo.add_sentences(lecture_id, sentences)
        by_idx = {s["idx"]: s for s in stored}

        proposed = self.llm.extract_entries(sentences, self.key) if sentences else []
        entries = self.repo.add_entries(session_id, [
            {"concept_id": p["concept_id"], "status": p["status"],
             "misconception_id": p["misconception_id"], "sentence_id": by_idx[p["sentence_idx"]]["id"]}
            for p in proposed
        ])
        for e in entries:
            e["sentence"] = next(s for s in stored if s["id"] == e["sentence_id"])
        return {
            "lecture": {"id": lecture_id, "kind": kind, "has_audio": audio_path is not None,
                        "transcript_source": source, "text": text},
            "sentences": stored,
            "proposed_entries": entries,
            "warning": warning,
        }

    # 5-6. Confirm and write to Notebook (new entry supersedes old, never delete)
    def confirm(self, session_id: str, lecture_id: int, entry_ids: list[int],
                edits: list[dict] | None = None, additions: list[dict] | None = None) -> dict:
        all_entries = {e["id"]: e for e in self.repo.list_entries(session_id)}
        for ed in edits or []:
            e = all_entries.get(ed["entry_id"])
            if not e or e["sentence"]["lecture_id"] != lecture_id:
                continue
            fields = self._validated(ed)
            self.repo.update_entry(e["id"], **fields)
        new_ids = []
        sentence_ids = {s["id"] for lec in self.repo.list_lectures(session_id) if lec["id"] == lecture_id
                        for s in lec["sentences"]}
        for add in additions or []:
            if add.get("sentence_id") not in sentence_ids:
                continue
            fields = self._validated(add)
            new_ids += [e["id"] for e in self.repo.add_entries(session_id, [{**fields, "sentence_id": add["sentence_id"]}])]

        all_entries = {e["id"]: e for e in self.repo.list_entries(session_id)}
        to_confirm = [all_entries[i] for i in [*entry_ids, *new_ids]
                      if i in all_entries and all_entries[i]["sentence"]["lecture_id"] == lecture_id
                      and not all_entries[i]["confirmed"]]
        to_confirm.sort(key=lambda e: (e["sentence"]["idx"], e["id"]))
        for e in to_confirm:
            current = self.active_notebook(session_id).get(e["concept_id"])
            self.repo.update_entry(e["id"], confirmed=1)
            if current:
                self.repo.update_entry(current["id"], superseded_by=e["id"])
        return self.notebook(session_id)

    def _validated(self, d: dict) -> dict:
        cid, status, mid = d.get("concept_id"), d.get("status"), d.get("misconception_id") or None
        if cid not in self.key.concept_ids or status not in (CORRECT, MISCONCEPTION):
            raise ValueError(f"invalid entry {d}")
        if status == CORRECT:
            mid = None
        elif mid is not None and self.key.misconception_ids.get(mid) != cid:
            raise ValueError(f"misconception {mid} does not belong to {cid}")
        return {"concept_id": cid, "status": status, "misconception_id": mid}

    def active_notebook(self, session_id: str) -> dict[str, dict]:
        """concept_id -> latest confirmed, non superseded entry"""
        out = {}
        for e in self.repo.list_entries(session_id, confirmed_only=True):
            if e["superseded_by"] is None:
                out[e["concept_id"]] = e  # ordered by id, so the newest wins
        return out

    def notebook(self, session_id: str) -> dict:
        active = self.active_notebook(session_id)
        return {
            "entries": self.repo.list_entries(session_id, confirmed_only=True),
            "concepts": [
                {"id": c["id"], "label": c["label"], "description": c["description"],
                 "status": concept_status(active, c["id"]), "entry": active.get(c["id"])}
                for c in self.key.concepts
            ],
        }

    def search_notebook(self, session_id: str, q: str = "", concept_id: str | None = None) -> list[dict]:
        """Non superseded entries matching q (case insensitive on concept id, label, sentence text)."""
        active = self.active_notebook(session_id)
        edges = self.repo.list_edges()
        needle = (q or "").strip().lower()
        out = []
        for e in self.repo.list_entries(session_id):
            if e["superseded_by"] is not None:
                continue
            cid = e["concept_id"]
            if concept_id and cid != concept_id:
                continue
            label = self.key.label(cid)
            text = e["sentence"]["text"]
            if needle and not any(needle in s.lower() for s in (cid, label, text)):
                continue
            neighbors = []
            for s, t in edges:
                other = t if s == cid else s if t == cid else None
                if other and other not in [n["concept_id"] for n in neighbors]:
                    neighbors.append({"concept_id": other, "status": concept_status(active, other)})
            out.append({"entry_id": e["id"], "concept_id": cid, "label": label, "status": e["status"],
                        "misconception_id": e["misconception_id"], "confirmed": e["confirmed"],
                        "sentence_id": e["sentence_id"], "text": text,
                        "start_ms": e["sentence"]["start_ms"], "end_ms": e["sentence"]["end_ms"],
                        "neighbors": neighbors})
        return out

    # 7-9. Grade with code, phrase, return linked data
    def take_exam(self, session_id: str) -> dict:
        questions = self.repo.list_questions()
        results = grade_exam(questions, self.active_notebook(session_id))
        self._attach_lines(questions, results)
        score = sum(r["is_correct"] for r in results)
        attempt_id, attempt_no = self.repo.create_attempt(session_id, score)
        self.repo.add_answers(attempt_id, results)
        return {
            "attempt_id": attempt_id, "attempt_no": attempt_no, "score": score, "total": len(results),
            "passed": score >= self.pass_threshold * len(results),
            "results": results,
            "office_hours": self.office_hours(session_id),
        }

    def _attach_lines(self, questions: list[dict], results: list[dict]) -> None:
        """LLM (or persona) phrases each graded result; the template is the last resort. Answers never change."""
        for q, r in zip(questions, results):
            try:
                r["line"] = self.llm.phrase(r, q, self.key) or template_phrase(r, q, self.key)
            except Exception:  # noqa: BLE001
                r["line"] = template_phrase(r, q, self.key)
            r["question"] = {k: q[k] for k in ("id", "type", "prompt", "options", "required_concepts")}

    # Daily loop: a 3 question round, a streak, and Reeta's mood
    def weak_concepts(self, session_id: str) -> list[tuple[str, str]]:
        """[(concept_id, status)]: misconceptions first, then missing, each in Answer key order."""
        active = self.active_notebook(session_id)
        status = {cid: concept_status(active, cid) for cid in self.key.concept_ids}
        return ([(c, MISCONCEPTION) for c in self.key.concept_ids if status[c] == MISCONCEPTION]
                + [(c, "missing") for c in self.key.concept_ids if status[c] == "missing"])

    def pick_loop_questions(self, session_id: str, n: int = 3) -> tuple[list[dict], int | None]:
        """Up to n questions: just taught concepts first, then weakest concepts, then fill in exam order."""
        questions = self.repo.list_questions()
        lectures = self.repo.list_lectures(session_id)
        lecture_id = lectures[-1]["id"] if lectures else None
        just_taught = {e["concept_id"] for e in self.repo.list_entries(session_id, confirmed_only=True)
                       if e["sentence"]["lecture_id"] == lecture_id}
        ordered = [q for q in questions if just_taught & set(q["required_concepts"])]
        for cid, _ in self.weak_concepts(session_id):
            ordered += [q for q in questions if cid in q["required_concepts"]]
        ordered += questions
        picked, seen = [], set()
        for q in ordered:
            if q["id"] not in seen:
                seen.add(q["id"])
                picked.append(q)
        return picked[:n], lecture_id

    def loop_quiz(self, session_id: str) -> dict:
        questions, lecture_id = self.pick_loop_questions(session_id)
        results = grade_exam(questions, self.active_notebook(session_id))
        self._attach_lines(questions, results)
        score, total = sum(r["is_correct"] for r in results), len(results)
        passed = total > 0 and score == total
        concept_ids = [c for c in self.key.concept_ids if any(c in q["required_concepts"] for q in questions)]
        round_id = self.repo.add_round(session_id, self.clock().isoformat(timespec="seconds"), lecture_id,
                                       score, total, passed, concept_ids)
        return {
            "round_id": round_id, "score": score, "total": total, "passed": passed,
            "mood": "proud" if passed else "confused",
            "result_line": persona.result_line(score, total),
            "results": results,
            "streak": self._streaks(session_id)[0],
        }

    def _streaks(self, session_id: str) -> tuple[int, int]:
        """(current, best) from the calendar days that have at least one passed round."""
        days = {_day(r) for r in self.repo.list_rounds(session_id) if r["passed"]}
        return current_streak(days, self.clock().date()), best_streak(days)

    def loop_today(self, session_id: str) -> dict:
        today = self.clock().date()
        rounds = self.repo.list_rounds(session_id)
        streak, best = self._streaks(session_id)
        last = rounds[-1] if rounds else None
        days_since = (today - _day(last)).days if last else None

        if days_since is not None and days_since >= 2:
            mood = "sad"
        elif last and not last["passed"]:
            mood = "confused"
        elif any(r["passed"] and _day(r) == today for r in rounds):
            mood = "proud"
        else:
            mood = "listening"

        weak = self.weak_concepts(session_id)
        if weak:
            ask_id, reason = weak[0]
        else:  # everything taught right: review the concept rounds covered least recently (never covered first)
            last_seen = {c: r["id"] for r in rounds for c in r["concept_ids"]}
            ask_id = min(self.key.concept_ids, key=lambda c: (last_seen.get(c, 0), self.key.concept_ids.index(c)))
            reason = "review"
        label = self.key.label(ask_id)

        active = self.active_notebook(session_id)
        mastered = sum(concept_status(active, c) == CORRECT for c in self.key.concept_ids)
        return {
            "streak": streak, "best_streak": best,
            "last_round_at": last["created_at"] if last else None,
            "days_since_last": days_since,
            "mood": mood,
            "ask": {"concept_id": ask_id, "label": label, "reason": reason},
            "line": persona.greeting(mood, streak, label, days_missed=(days_since or 1) - 1),
            "progress": {"mastered": mastered, "total": len(self.key.concept_ids)},
            "level": level_for(mastered),
        }

    # 10. Office hours: only the concepts the AI student failed on
    def office_hours(self, session_id: str) -> list[dict]:
        attempts = self.repo.list_attempts(session_id)
        if not attempts:
            return []
        failed = []
        for a in attempts[-1]["answers"]:
            if not a["is_correct"]:
                failed += [c for c in a["concept_ids"] if c not in failed]
        active = self.active_notebook(session_id)
        out = []
        for cid in [c for c in self.key.concept_ids if c in failed]:
            concept, entry = self.key.concept(cid), active.get(cid)
            status = concept_status(active, cid)
            if status == MISCONCEPTION:
                ask = (f"You told me “{entry['sentence']['text']}”, but I got questions about "
                       f"{concept['label'].lower()} wrong. Can you explain it again?")
            elif status == "missing":
                ask = concept["student_question"]
            else:
                ask = f"I think I get {concept['label'].lower()} now. Ready for the retake?"
            out.append({"concept_id": cid, "label": concept["label"], "status": status,
                        "question": ask, "entry": entry})
        return out

    def report(self, session_id: str) -> dict:
        attempts = self.repo.list_attempts(session_id)
        all_entries = self.repo.list_entries(session_id, confirmed_only=True)
        active = self.active_notebook(session_id)
        concepts = []
        for c in self.key.concepts:
            history = [e for e in all_entries if e["concept_id"] == c["id"]]
            failed_in = [a["attempt_no"] for a in attempts
                         if any(not ans["is_correct"] and c["id"] in ans["concept_ids"] for ans in a["answers"])]
            status = concept_status(active, c["id"])
            if status == "missing":
                grade, comment = "F", "Never taught. The AI student had nothing in its Notebook."
            elif status == MISCONCEPTION:
                grade, comment = "D", "Taught wrong. The AI student learned a misconception from you."
            elif history and history[0]["status"] == CORRECT and not failed_in:
                grade, comment = "A", "Taught clearly the first time."
            else:
                grade, comment = "B", "Fixed in Office hours after the AI student struggled."
            concepts.append({"id": c["id"], "label": c["label"], "status": status, "grade": grade,
                             "comment": comment, "history": history, "failed_in_attempts": failed_in})
        total = len(self.repo.list_questions())
        last = attempts[-1] if attempts else None
        return {
            "concepts": concepts,
            "attempts": [{"attempt_no": a["attempt_no"], "score": a["score"], "total": total} for a in attempts],
            "passed": bool(last and last["score"] >= self.pass_threshold * total),
            "lectures": len(self.repo.list_lectures(session_id)),
        }


def _day(round_row: dict) -> date:
    return datetime.fromisoformat(round_row["created_at"]).date()


def current_streak(days: set[date], today: date) -> int:
    """Consecutive days with a passed round, ending today or yesterday (a streak survives until tonight)."""
    day = today if today in days else today - timedelta(days=1)
    n = 0
    while day in days:
        n, day = n + 1, day - timedelta(days=1)
    return n


def best_streak(days: set[date]) -> int:
    best = 0
    for d in days:
        if d - timedelta(days=1) not in days:  # start of a run
            n = 1
            while d + timedelta(days=n) in days:
                n += 1
            best = max(best, n)
    return best


def level_for(mastered: int) -> str:
    """Freshman 0 to 1 mastered, Sophomore 2, Junior 3 to 4, Graduate 5."""
    if mastered >= 5:
        return "Graduate"
    if mastered >= 3:
        return "Junior"
    if mastered == 2:
        return "Sophomore"
    return "Freshman"


def _clean_client_sentences(raw: list[dict]) -> list[dict]:
    out = []
    for s in raw:
        text = str(s.get("text", "")).strip()
        if text:
            out.append({"idx": len(out), "text": text,
                        "start_ms": int(s.get("start_ms") or 0), "end_ms": int(s.get("end_ms") or 0)})
    return out
