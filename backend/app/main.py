"""FastAPI app. Providers are chosen by SPEECH_PROVIDER / LLM_PROVIDER / DB_PROVIDER."""
import json
import mimetypes
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import settings
from .content import load_answer_key, load_exam
from .llm.base import get_llm_client
from .repo.base import get_repository
from .service import ReetaService
from .speech.base import get_speech_client


def build_service() -> ReetaService:
    key = load_answer_key(settings.content_dir)
    repo = get_repository(settings.db_provider)
    repo.seed_content(key.concepts, load_exam(settings.content_dir, key), key.edges)
    return ReetaService(repo, get_speech_client(settings.speech_provider), get_llm_client(settings.llm_provider),
                        key, settings.audio_dir, settings.pass_threshold)


app = FastAPI(title="Reeta: teach the AI student")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
svc = build_service()

Session = Header(default="demo", alias="X-Session-Id")


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
    lec = svc.repo.get_lecture(lecture_id)
    if not lec or lec["session_id"] != session_id:
        raise HTTPException(404, "Lecture not found")
    try:
        return svc.confirm(session_id, lecture_id, body.entry_ids, body.edits, body.additions)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/lectures")
def lectures(session_id: str = Session):
    return {"lectures": [{k: v for k, v in lec.items() if k != "audio_path"} | {"has_audio": bool(lec["audio_path"])}
                         for lec in svc.repo.list_lectures(session_id)]}


@app.get("/lectures/{lecture_id}/audio")
def lecture_audio(lecture_id: int):
    lec = svc.repo.get_lecture(lecture_id)
    if not lec or not lec["audio_path"] or not Path(lec["audio_path"]).exists():
        raise HTTPException(404, "No audio for this Lecture")
    return FileResponse(lec["audio_path"])


@app.get("/notebook")
def notebook(session_id: str = Session):
    return svc.notebook(session_id)


@app.get("/notebook/search")
def notebook_search(q: str = "", concept_id: str | None = None, session_id: str = Session):
    return {"q": q, "concept_id": concept_id, "results": svc.search_notebook(session_id, q, concept_id)}


@app.get("/concepts/edges")
def concept_edges():
    return {"edges": [list(e) for e in svc.repo.list_edges()]}


@app.post("/exam/take")
def take_exam(session_id: str = Session):
    return svc.take_exam(session_id)


@app.get("/office-hours")
def office_hours(session_id: str = Session):
    return {"concepts": svc.office_hours(session_id)}


@app.get("/report")
def report(session_id: str = Session):
    return svc.report(session_id)


@app.post("/session/reset")
def reset(session_id: str = Session):
    svc.repo.reset_session(session_id)
    return {"ok": True}
