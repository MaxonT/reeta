"""FastAPI app. Providers are chosen by SPEECH_PROVIDER / LLM_PROVIDER / DB_PROVIDER."""
import json
import mimetypes
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .accounts import Accounts
from .classwork import Classwork
from .config import settings
from .content import load_answer_key, load_exam
from .llm.base import get_llm_client
from .repo.base import get_repository
from .service import ReetaService
from .sessions import is_reserved, notes_session_for, topic_of
from .sources import MAX_UPLOAD_BYTES, SourceError
from .speech.base import get_speech_client


def build_service() -> ReetaService:
    key = load_answer_key(settings.content_dir)
    repo = get_repository(settings.db_provider)
    repo.seed_content(load_exam(settings.content_dir, key))
    return ReetaService(repo, get_speech_client(settings.speech_provider), get_llm_client(settings.llm_provider),
                        key, settings.audio_dir, settings.pass_threshold,
                        settings.max_source_chars, settings.max_notes_chars)


app = FastAPI(title="Reeta: teach the AI student")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
svc = build_service()
accounts = Accounts(svc.repo, settings.pass_threshold)
app.include_router(accounts.router)
classwork = Classwork(svc, accounts, MAX_UPLOAD_BYTES)
app.include_router(classwork.router)

# Logged in: the account's session. Otherwise the X-Session-Id header, default "demo".
Session = Depends(accounts.session_id)


def _no_longer_supported(what: str):
    """The notebook flow's storage was dropped, so its endpoints answer 410 instead of crashing with a 500."""
    raise HTTPException(410, f"{what} is no longer supported. Use the live exam (POST /exam/run).")


class ConfirmBody(BaseModel):
    entry_ids: list[int] = []
    edits: list[dict] = []       # [{entry_id, concept_id, status, misconception_id}]
    additions: list[dict] = []   # [{sentence_id, concept_id, status, misconception_id}]


@app.get("/health")
def health():
    return {"ok": True, "speech": settings.speech_provider, "llm": settings.llm_provider, "db": settings.db_provider}


@app.get("/answer-key")
def answer_key():
    """Concept and misconception labels for the UI (no exam answers)."""
    return {"topic": svc.key.topic, "concepts": [
        {"id": c["id"], "label": c["label"], "description": c["description"],
         "misconceptions": [{"id": m["id"], "description": m["description"]} for m in c["misconceptions"]]}
        for c in svc.key.concepts]}


@app.post("/lectures/audio")
async def post_lecture_audio(
    audio: UploadFile | None = File(default=None),
    kind: str = Form(default="lecture"),
    transcript: str | None = Form(default=None, description="JSON [{text,start_ms,end_ms}] from Web Speech API"),
    text: str | None = Form(default=None, description="typed Lecture, last resort"),
    session_id: str = Session,
):
    data = await audio.read() if audio else None
    ext = Path(audio.filename or "").suffix if audio else ""
    if audio and not ext:
        ext = mimetypes.guess_extension((audio.content_type or "").split(";")[0]) or ".webm"
    client_sentences = json.loads(transcript) if transcript else None
    if not data and not client_sentences and not (text and text.strip()):
        raise HTTPException(400, "Send audio, a transcript, or text")
    return svc.ingest_lecture(session_id, kind if kind in ("lecture", "office_hours") else "lecture",
                              data or None, ext, client_sentences, text)


@app.post("/lectures/{lecture_id}/confirm")
def confirm(lecture_id: int, body: ConfirmBody, session_id: str = Session):
    _no_longer_supported("Confirming lecture entries")


@app.get("/lectures")
def lectures(session_id: str = Session):
    return {"lectures": [{k: v for k, v in lec.items() if k != "audio_path"} | {"has_audio": bool(lec["audio_path"])}
                         for lec in svc.repo.list_lectures(session_id)]}


@app.get("/lectures/{lecture_id}/audio")
def lecture_audio(lecture_id: int, session_id: str = Session):
    lec = svc.repo.get_lecture(lecture_id)
    if not lec or lec["session_id"] != session_id or not lec["audio_path"] or not Path(lec["audio_path"]).exists():
        raise HTTPException(404, "No audio for this Lecture")
    return FileResponse(lec["audio_path"])


@app.get("/notebook")
def notebook(session_id: str = Session):
    _no_longer_supported("The notebook")


@app.post("/sources")
async def post_source(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None, description="pasted notes, used when no file is sent"),
    session_id: str = Session,
):
    """Add source material the exam questions are written from. A file (.txt, .md, .pdf, .docx) or pasted text."""
    _no_topic_notes(session_id)
    data = None
    if file:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "That file is too large.")
    try:
        return svc.add_source(session_id, file.filename if file else None, data, text)
    except SourceError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


def _no_topic_notes(session_id: str):
    if topic_of(session_id) is not None:
        raise HTTPException(403, "A topic's notes come from your teacher.")


@app.get("/sources")
def sources(session_id: str = Session):
    """On a topic: the teacher's notes for it."""
    return {"sources": svc.list_sources(notes_session_for(session_id))}


@app.delete("/sources/{source_id}")
def delete_source(source_id: int, session_id: str = Session):
    _no_topic_notes(session_id)
    if not svc.delete_source(session_id, source_id):
        raise HTTPException(404, "Source not found")
    return {"ok": True}


def _sse(events):
    """{"event", "data"} dicts -> Server-Sent Events text. A failure mid-stream becomes an error event."""
    try:
        for ev in events:
            yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'])}\n\n"
    except Exception as exc:  # noqa: BLE001
        yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"


@app.post("/exam/run")
def run_exam(questions: int = 5, session_id: str = Session):
    """Streams the live exam: questions, Reeta's answers as they are typed, then grades. See FRONTEND_CHANGES.md."""
    topic_id = topic_of(session_id)
    if topic_id is not None:  # the teacher sets a topic's quiz length, and its notes are the only material
        if not svc.repo.list_sources(notes_session_for(session_id)):
            raise HTTPException(409, "Your teacher has not added notes for this topic yet.")
        questions = classwork.questions_for(topic_id) or questions
    return StreamingResponse(_sse(svc.run_exam(session_id, max(1, min(questions, 10)))),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/exam/take")
def take_exam(session_id: str = Session):
    _no_longer_supported("The notebook exam")


@app.get("/office-hours")
def office_hours(session_id: str = Session):
    _no_longer_supported("The office hours list")


@app.get("/report")
def report(session_id: str = Session):
    _no_longer_supported("The report card")


@app.post("/session/reset")
def reset(session_id: str = Session):
    if is_reserved(session_id):  # an account's attempts are its gradebook
        raise HTTPException(403, "Accounts cannot be reset.")
    svc.repo.reset_session(session_id)
    return {"ok": True}
