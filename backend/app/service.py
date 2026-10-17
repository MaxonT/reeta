"""Business logic. Talks only to the SpeechClient / LLMClient / Repository interfaces."""
from pathlib import Path

from .content import AnswerKey
from .grading import CORRECT, MISCONCEPTION, NOT_TAUGHT, concept_status, grade_exam
from .llm.base import LLMClient, template_phrase
from .repo.base import Repository
from .speech.base import SpeechClient


class ReetaService:
    def __init__(self, repo: Repository, speech: SpeechClient, llm: LLMClient, key: AnswerKey,
                 audio_dir: Path, pass_threshold: float = 1.0):
        self.repo, self.speech, self.llm, self.key = repo, speech, llm, key
        self.audio_dir = audio_dir
        self.pass_threshold = pass_threshold

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

    # 7-9. Grade with code, phrase, return linked data
    def take_exam(self, session_id: str) -> dict:
        questions = self.repo.list_questions()
        results = grade_exam(questions, self.active_notebook(session_id))
        for q, r in zip(questions, results):
            try:
                r["line"] = self.llm.phrase(r, q, self.key) or template_phrase(r, q, self.key)
            except Exception:  # noqa: BLE001
                r["line"] = template_phrase(r, q, self.key)
            r["question"] = {k: q[k] for k in ("id", "type", "prompt", "options", "required_concepts")}
        score = sum(r["is_correct"] for r in results)
        attempt_id, attempt_no = self.repo.create_attempt(session_id, score)
        self.repo.add_answers(attempt_id, results)
        return {
            "attempt_id": attempt_id, "attempt_no": attempt_no, "score": score, "total": len(results),
            "passed": score >= self.pass_threshold * len(results),
            "results": results,
            "office_hours": self.office_hours(session_id),
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


def _clean_client_sentences(raw: list[dict]) -> list[dict]:
    out = []
    for s in raw:
        text = str(s.get("text", "")).strip()
        if text:
            out.append({"idx": len(out), "text": text,
                        "start_ms": int(s.get("start_ms") or 0), "end_ms": int(s.get("end_ms") or 0)})
    return out
