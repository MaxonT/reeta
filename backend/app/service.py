"""Business logic. Talks only to the SpeechClient / LLMClient / Repository interfaces."""
import random
from collections import deque
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .exam import AnswerStream, transcripts_text, verify_quotes
from .llm.base import RESET, LLMClient
from .repo.base import Repository
from .sessions import notes_session_for
from .sources import PASTED, clean_text, combine_sources, extract_text
from .speech.base import SpeechClient
from .words import sentences_to_words


class ReetaService:
    def __init__(self, repo: Repository, speech: SpeechClient, llm: LLMClient,
                 audio_dir: Path, pass_threshold: float = 1.0,
                 max_source_chars: int = 50_000, max_notes_chars: int = 60_000):
        self.repo, self.speech, self.llm = repo, speech, llm
        self.rng = random.Random()
        self.audio_dir = audio_dir
        self.pass_threshold = pass_threshold
        self.max_source_chars, self.max_notes_chars = max_source_chars, max_notes_chars

    # Source material the exam is written from. Raises SourceError for a bad upload.
    def add_source(self, session_id: str, filename: str | None, data: bytes | None, text: str | None) -> dict:
        if data is not None:
            name = filename or "upload"
            clean = extract_text(name, data, self.max_source_chars)
        else:
            name, clean = PASTED, clean_text(text or "", self.max_source_chars)
        return {"id": self.repo.add_source(session_id, name, clean), "filename": name, "chars": len(clean)}

    def list_sources(self, session_id: str) -> list[dict]:
        return [{"id": s["id"], "filename": s["filename"], "chars": len(s["text"]), "created_at": s["created_at"]}
                for s in self.repo.list_sources(session_id)]

    def delete_source(self, session_id: str, source_id: int) -> bool:
        return self.repo.delete_source(session_id, source_id)

    # 1-3. Record, transcribe (Whisper words), store
    def ingest_lecture(self, session_id: str, kind: str, audio: bytes | None, audio_ext: str,
                       client_sentences: list[dict] | None, typed_text: str | None) -> dict:
        lecture_id = self.repo.create_lecture(session_id, kind, "")
        audio_path = None
        if audio:
            self.audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = self.audio_dir / f"lecture_{lecture_id}{audio_ext}"
            audio_path.write_bytes(audio)
            self.repo.update_lecture(lecture_id, audio_path=str(audio_path))

        transcript, source, warning = None, None, None
        if audio_path is not None:
            try:
                transcript, source = self.speech.transcribe(audio_path), "server"
            except NotImplementedError:
                pass
            except Exception as exc:  # noqa: BLE001 fall back to the browser transcript
                warning = f"Server transcription failed ({exc.__class__.__name__}); used browser transcript."
        if not (transcript and transcript["text"]) and client_sentences:
            sentences = _clean_client_sentences(client_sentences)
            transcript = {"text": " ".join(s["text"] for s in sentences), "words": sentences_to_words(sentences)}
            source = "browser"
        if not (transcript and transcript["text"]) and typed_text and typed_text.strip():
            transcript, source = {"text": typed_text.strip(), "words": []}, "typed"
        transcript = transcript or {"text": "", "words": []}

        self.repo.update_lecture(lecture_id, text=transcript["text"], words=transcript["words"])
        return {
            "lecture": {"id": lecture_id, "kind": kind, "has_audio": audio_path is not None,
                        "transcript_source": source, "text": transcript["text"], "words": transcript["words"]},
            "warning": warning,
        }

    # 4. Live exam: questions from the course notes, Reeta answers from the transcripts, a judge grades.
    # A generator of {"event", "data"} dicts so the endpoint can stream them as they happen.
    def _written_questions(self, session_id: str, n: int) -> list[dict]:
        """[{prompt, reference_answer}] from the LLM question writer."""
        # a topic session quizzes on the teacher's notes for that topic
        notes = combine_sources(self.repo.list_sources(notes_session_for(session_id)), self.max_notes_chars)
        if not notes:
            raise ValueError("there are no notes to write questions from. Upload the teacher's document first")
        return self.llm.generate_questions(n, notes)

    def run_exam(self, session_id: str, n: int = 5) -> Iterator[dict]:
        # Reeta knows the newest lecture plus the office hours recorded after it. Older lectures drop out, and
        # blank ones (a failed upload) are skipped.
        taught = [lec for lec in self.repo.list_lectures(session_id) if (lec.get("text") or "").strip()]
        start = max((i for i, lec in enumerate(taught) if lec["kind"] == "lecture"), default=0)
        lectures = taught[start:]
        transcripts = transcripts_text(lectures)
        try:
            questions = [{"id": f"q{i}", **q} for i, q in enumerate(self._written_questions(session_id, n), 1)]
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": {"message": f"Could not write the exam: {exc}"}}
            return
        attempt_id, attempt_no = self.repo.create_attempt(session_id)
        yield {"event": "questions", "data": {"attempt_id": attempt_id, "attempt_no": attempt_no,
                                              "questions": [{"id": q["id"], "prompt": q["prompt"]} for q in questions]}}
        score = 0
        pending: deque = deque()  # (row, future or None) in question order

        def flush(block: bool):
            nonlocal score
            while pending and (block or pending[0][1] is None or pending[0][1].done()):
                row, future = pending.popleft()
                if future is not None:
                    try:
                        verdict = future.result()
                        row["is_correct"], row["feedback"] = bool(verdict["is_correct"]), verdict.get("feedback", "")
                        supported = verdict.get("supported", True)
                    except Exception:  # noqa: BLE001
                        row["is_correct"], row["feedback"], supported = False, "Could not grade this answer.", True
                    row["reason"] = "correct" if row["is_correct"] else "wrong" if supported else "not_taught"
                    if not supported:  # the quote does not back the answer: treat it as never taught
                        row.update(answer=None, lecture_id=None, quote=None, quote_start_ms=None, quote_end_ms=None)
                score += int(row["is_correct"])
                self.repo.add_answers(attempt_id, [row])
                yield {"event": "graded", "data": {"id": row["question_id"], "is_correct": row["is_correct"],
                                                   "reason": row["reason"], "feedback": row["feedback"]}}

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                for q in questions:
                    yield {"event": "question_start", "data": {"id": q["id"]}}
                    stream = AnswerStream()
                    for chunk in self.llm.answer_stream(q["prompt"], transcripts):
                        if chunk == RESET:  # the fallback model restarted the answer
                            stream = AnswerStream()
                            yield {"event": "answer_reset", "data": {"id": q["id"]}}
                            continue
                        text = stream.feed(chunk)
                        if text:
                            yield {"event": "answer_delta", "data": {"id": q["id"], "text": text}}
                    line, quotes_raw = stream.finish_all()
                    verified = verify_quotes(quotes_raw, lectures)  # never trust the model's quotes
                    found = verified[0] if verified else None  # the first one fills the single quote fields
                    row = {"question_id": q["id"], "prompt": q["prompt"], "reference_answer": q["reference_answer"],
                           "answer": line if found else None, "line": line, "is_correct": False,
                           "reason": "not_taught", "feedback": None, "lecture_id": None, "quote": None,
                           "quote_start_ms": None, "quote_end_ms": None}
                    if found:
                        row.update(lecture_id=found["lecture_id"], quote=found["quote"],
                                   quote_start_ms=found["start_ms"], quote_end_ms=found["end_ms"])
                    yield {"event": "answer_done", "data": {
                        "id": q["id"], "line": line, "supported": bool(found), "lecture_id": row["lecture_id"],
                        "quote": row["quote"], "quote_start_ms": row["quote_start_ms"],
                        "quote_end_ms": row["quote_end_ms"],
                        "quotes": [{"lecture_id": f["lecture_id"], "quote": f["quote"],
                                    "quote_start_ms": f["start_ms"], "quote_end_ms": f["end_ms"]} for f in verified]}}
                    if found:
                        # the judge sees every verified passage, so a claim none of them states is unsupported
                        passages = " [...] ".join(f["quote"] for f in verified)
                        pending.append((row, pool.submit(self.llm.judge, q["prompt"], q["reference_answer"], line,
                                                         passages)))
                    else:
                        row["feedback"] = ("You never taught Reeta this." if not quotes_raw
                                           else f"Reeta's quote is not in your lectures, so it does not count: "
                                                f"“{quotes_raw[0][:200]}”")
                        pending.append((row, None))
                    yield from flush(block=False)
                yield from flush(block=True)
        finally:
            self.repo.set_attempt_score(attempt_id, score)
        yield {"event": "done", "data": {"attempt_id": attempt_id, "attempt_no": attempt_no, "score": score,
                                         "total": len(questions),
                                         "passed": score >= self.pass_threshold * len(questions)}}

    def active_notebook(self, session_id: str) -> dict[str, dict]:
        """concept_id -> latest confirmed, non superseded entry"""
        out = {}
        for e in self.repo.list_entries(session_id, confirmed_only=True):
            if e["superseded_by"] is None:
                out[e["concept_id"]] = e  # ordered by id, so the newest wins
        return out


def _clean_client_sentences(raw: list[dict]) -> list[dict]:
    out = []
    for s in raw:
        text = str(s.get("text", "")).strip()
        if text:
            out.append({"idx": len(out), "text": text,
                        "start_ms": int(s.get("start_ms") or 0), "end_ms": int(s.get("end_ms") or 0)})
    return out
