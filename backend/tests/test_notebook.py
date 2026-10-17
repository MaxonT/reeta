"""Notebook rules: only confirmed entries count, new entries supersede old ones, nothing is deleted."""
from app.llm.mock import MockLLMClient
from app.sentences import segments_to_sentences

from .conftest import teach

FULL_LECTURE = (
    "A recursive function is a function that calls itself. "
    "Every recursive function needs a base case, otherwise you get infinite recursion and a RecursionError. "
    "Each call should work on a smaller problem, like n minus 1. "
    "Every call gets its own stack frame with its own local variables. "
    "The return value passes back up to the caller, one call at a time."
)


def test_mock_extracts_all_five_concepts(svc):
    out = svc.ingest_lecture("s1", "lecture", None, "", None, FULL_LECTURE)
    assert {e["concept_id"] for e in out["proposed_entries"]} == set(svc.key.concept_ids)
    assert all(e["status"] == "correct" for e in out["proposed_entries"])


def test_mock_detects_misconceptions_and_negation(key):
    mock = MockLLMClient()
    sents = [{"idx": 0, "text": "Honestly you don't need a base case."},
             {"idx": 1, "text": "Recursion does not stop by itself."},
             {"idx": 2, "text": "All the calls share the same variables."},
             {"idx": 3, "text": "Only the last call's return value matters."},
             {"idx": 4, "text": "Let's get lunch."}]
    got = {(e["sentence_idx"], e["concept_id"]): (e["status"], e["misconception_id"])
           for e in mock.extract_entries(sents, key)}
    assert got[(0, "base_case")] == ("misconception", "base_case_not_needed")
    assert got[(1, "base_case")] == ("correct", None)
    assert got[(2, "independent_frames")] == ("misconception", "frames_shared_variables")
    assert got[(3, "return_propagation")] == ("misconception", "return_only_last")
    assert not any(idx == 4 for idx, _ in got)


def test_unconfirmed_entries_do_not_count(svc):
    svc.ingest_lecture("s1", "lecture", None, "", None, FULL_LECTURE)
    assert svc.active_notebook("s1") == {}
    assert svc.take_exam("s1")["score"] == 0


def test_full_lecture_passes_exam(svc):
    teach(svc, FULL_LECTURE)
    exam = svc.take_exam("s1")
    assert exam["score"] == exam["total"] == 10 and exam["passed"]
    assert all(r["line"] for r in exam["results"])


def test_office_hours_supersedes_misconception_and_keeps_history(svc):
    teach(svc, "A function can call itself. Recursion stops by itself, so you can relax.")
    first = svc.take_exam("s1")
    assert not first["passed"]
    q2 = next(r for r in first["results"] if r["question_id"] == "q2")
    assert q2["reason"] == "misconception" and q2["answer"] == "It stops by itself once the work is done"
    assert q2["citations"][0]["text"] == "Recursion stops by itself, so you can relax."
    oh_ids = {c["concept_id"] for c in first["office_hours"]}
    assert "base_case" in oh_ids and "return_propagation" in oh_ids

    old = svc.active_notebook("s1")["base_case"]
    teach(svc, "Correction: recursion needs a base case or it never stops.", kind="office_hours")
    new = svc.active_notebook("s1")["base_case"]
    assert new["status"] == "correct" and new["id"] != old["id"]

    history = [e for e in svc.repo.list_entries("s1", confirmed_only=True) if e["concept_id"] == "base_case"]
    assert [e["id"] for e in history] == [old["id"], new["id"]]
    assert history[0]["superseded_by"] == new["id"]

    second = svc.take_exam("s1")
    assert next(r for r in second["results"] if r["question_id"] == "q2")["is_correct"]
    assert second["attempt_no"] == 2


def test_report_grades_concepts(svc):
    teach(svc, "A function can call itself. Recursion stops by itself.")
    svc.take_exam("s1")
    teach(svc, FULL_LECTURE, kind="office_hours")
    svc.take_exam("s1")
    rep = {c["id"]: c for c in svc.report("s1")["concepts"]}
    assert rep["self_call"]["grade"] == "A"
    assert rep["base_case"]["grade"] == "B"
    assert svc.report("s1")["passed"]


def test_segments_to_sentences_keeps_timestamps():
    segs = [{"text": "Recursion is neat. A function", "start_ms": 0, "end_ms": 3000},
            {"text": "calls itself.", "start_ms": 3000, "end_ms": 4000}]
    out = segments_to_sentences(segs)
    assert [s["text"] for s in out] == ["Recursion is neat.", "A function calls itself."]
    assert out[0]["start_ms"] == 0 and 1500 <= out[0]["end_ms"] <= 2000
    assert 1800 <= out[1]["start_ms"] <= 2200 and out[1]["end_ms"] == 4000
