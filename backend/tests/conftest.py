import pytest

from app.config import settings
from app.content import load_answer_key, load_exam
from app.llm.mock import MockLLMClient
from app.repo.sqlite_repo import SQLiteRepository
from app.service import ReetaService
from app.speech.base import BrowserSpeechClient


@pytest.fixture
def key():
    return load_answer_key(settings.content_dir)


@pytest.fixture
def questions(key):
    return load_exam(settings.content_dir, key)


@pytest.fixture
def svc(key, questions, tmp_path):
    repo = SQLiteRepository(":memory:")
    repo.seed_content(key.concepts, questions, key.edges)
    return ReetaService(repo, BrowserSpeechClient(), MockLLMClient(), key, tmp_path / "audio")


def teach(svc, text, kind="lecture", session="s1"):
    """Typed Lecture, confirm every proposed entry."""
    out = svc.ingest_lecture(session, kind, None, "", None, text)
    svc.confirm(session, out["lecture"]["id"], [e["id"] for e in out["proposed_entries"]])
    return out
