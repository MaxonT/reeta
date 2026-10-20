import pytest

from app.llm.mock import MockLLMClient
from app.repo.sqlite_repo import SQLiteRepository
from app.service import ReetaService
from app.sources import PASTED, SourceError, clean_text, combine_sources, extract_text
from app.speech.base import BrowserSpeechClient


def test_extract_text_reads_txt_and_md_and_normalises():
    assert extract_text("notes.txt", b"  hello\r\nworld  ", 100) == "hello\nworld"
    assert extract_text("NOTES.MD", "# Title\ntext".encode(), 100) == "# Title\ntext"
    assert extract_text("n.txt", b"\xef\xbb\xbfwith bom", 100) == "with bom"      # utf-8 BOM stripped
    assert extract_text("n.txt", "caf\xe9".encode("latin-1"), 100) == "caf\xe9"  # not utf-8: latin-1 fallback


def test_extract_text_refuses_bad_uploads_with_the_right_status():
    with pytest.raises(SourceError) as e:
        extract_text("slides.pptx", b"PK", 100)
    assert e.value.status == 400 and ".pptx" in str(e.value) and ".pdf" in str(e.value) and ".docx" in str(e.value)
    with pytest.raises(SourceError) as e:
        extract_text("noext", b"text", 100)
    assert e.value.status == 400
    with pytest.raises(SourceError) as e:
        extract_text("n.txt", b"   \n  ", 100)
    assert e.value.status == 400 and "empty" in str(e.value)
    with pytest.raises(SourceError) as e:
        extract_text("n.txt", b"x" * 101, 100)
    assert e.value.status == 413


def test_clean_text_for_pasted_notes():
    assert clean_text("  pasted \x00text ", 100) == "pasted text"
    with pytest.raises(SourceError):
        clean_text("", 100)


def test_combine_sources_labels_each_source_and_caps_the_total():
    assert combine_sources([], 100) is None
    srcs = [{"filename": "a.txt", "text": "one"}, {"filename": PASTED, "text": "two"}]
    assert combine_sources(srcs, 1000) == f"## a.txt\none\n\n## {PASTED}\ntwo"
    assert combine_sources(srcs, 10) == "## a.txt\no"  # 9 characters of label, then 1 of text


class RecordsNotes(MockLLMClient):
    def generate_questions(self, n, notes):
        self.notes = notes
        return super().generate_questions(n, notes)


def make(tmp_path, llm=None):
    repo = SQLiteRepository(":memory:")
    return repo, ReetaService(repo, BrowserSpeechClient(), llm or MockLLMClient(), tmp_path / "audio")


def test_sources_are_per_session_and_reset_clears_them(tmp_path):
    repo, svc = make(tmp_path)
    a = svc.add_source("s1", "a.txt", b"first notes", None)
    b = svc.add_source("s1", None, None, "pasted bit")
    svc.add_source("s2", "other.txt", b"someone else", None)
    assert a["filename"] == "a.txt" and a["chars"] == len("first notes")
    assert b["filename"] == PASTED
    assert [s["filename"] for s in svc.list_sources("s1")] == ["a.txt", PASTED]
    assert "text" not in svc.list_sources("s1")[0]  # the list does not ship the full text
    assert svc.delete_source("s2", a["id"]) is False  # another session cannot delete it
    assert svc.delete_source("s1", a["id"]) is True and svc.delete_source("s1", a["id"]) is False
    repo.reset_session("s1")
    assert svc.list_sources("s1") == [] and len(svc.list_sources("s2")) == 1


def test_exam_without_any_notes_ends_with_an_error_event_and_never_calls_the_llm(tmp_path):
    llm = RecordsNotes()
    _, svc = make(tmp_path, llm)
    events = list(svc.run_exam("s1", 2))
    assert [e["event"] for e in events] == ["error"] and "notes" in events[0]["data"]["message"]
    assert not hasattr(llm, "notes")


def test_exam_questions_are_written_from_the_uploaded_notes(tmp_path):
    llm = RecordsNotes()
    repo, svc = make(tmp_path, llm)
    svc.add_source("s1", "notes.txt", b"Recursion needs a base case to stop. Each recursive call works on a smaller problem.", None)
    svc.ingest_lecture("s1", "lecture", None, "", None, "Every recursion needs a base case to stop.")
    events = list(svc.run_exam("s1", 2))

    assert "## notes.txt" in llm.notes
    questions = next(e["data"]["questions"] for e in events if e["event"] == "questions")
    assert len(questions) == 2 and all("notes say about" in q["prompt"] for q in questions)
    graded = {e["data"]["id"]: e["data"] for e in events if e["event"] == "graded"}
    assert graded["q1"]["is_correct"]                 # taught, and it matches the uploaded notes
    assert graded["q2"]["reason"] == "not_taught"     # never taught
    answers = repo.list_attempts("s1")[0]["answers"]
    assert answers[0]["reference_answer"].startswith("Recursion needs a base case")


def test_unusable_notes_end_the_exam_with_an_error_event(tmp_path):
    _, svc = make(tmp_path)
    svc.add_source("s1", None, None, "Too short.")
    events = list(svc.run_exam("s1", 2))
    assert [e["event"] for e in events] == ["error"]
