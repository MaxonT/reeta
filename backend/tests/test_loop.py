"""Reeta daily loop: 3 question rounds, streaks, mood, and the persona line bank."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import persona
from app.grading import grade_exam
from app.repo.sqlite_repo import SQLiteRepository
from app.service import ReetaService, best_streak, current_streak, level_for
from app.speech.base import BrowserSpeechClient
from app.llm.mock import MockLLMClient

from .conftest import teach
from .test_notebook import FULL_LECTURE


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, days: int):
        self.now += timedelta(days=days)


@pytest.fixture
def clock():
    return Clock(datetime(2026, 10, 17, 9, 30))


@pytest.fixture
def lsvc(key, questions, tmp_path, clock):
    repo = SQLiteRepository(":memory:")
    repo.seed_content(key.concepts, questions, key.edges)
    return ReetaService(repo, BrowserSpeechClient(), MockLLMClient(), key, tmp_path / "audio", clock=clock)


def test_quiz_picks_at_most_three_and_prefers_just_taught(lsvc):
    teach(lsvc, "Every call gets its own stack frame with its own local variables.")
    out = lsvc.loop_quiz("s1")
    assert out["total"] == len(out["results"]) <= 3
    ids = [r["question_id"] for r in out["results"]]
    assert ids[:2] == ["q6", "q7"]  # the only questions on independent_frames
    assert all("independent_frames" in r["question"]["required_concepts"] for r in out["results"][:2])
    assert lsvc.repo.list_rounds("s1")[0]["lecture_id"] == lsvc.repo.list_lectures("s1")[-1]["id"]


def test_quiz_then_prefers_weakest_concepts(lsvc):
    teach(lsvc, "A function can call itself.")
    teach(lsvc, "All the calls share the same variables.")
    teach(lsvc, "Let's get lunch.")  # latest lecture teaches nothing, so weakest concepts lead
    ids = [q["id"] for q in lsvc.pick_loop_questions("s1")[0]]
    assert ids == ["q6", "q7", "q2"]  # misconception (independent_frames) first, then missing base_case


def test_quiz_never_changes_grading(lsvc):
    teach(lsvc, "A function can call itself. Recursion stops by itself. Only the last call's return value matters.")
    out = lsvc.loop_quiz("s1")
    picked = {q["id"]: q for q in lsvc.repo.list_questions()}
    expected = grade_exam([picked[r["question_id"]] for r in out["results"]], lsvc.active_notebook("s1"))
    for got, exp in zip(out["results"], expected):
        assert {k: got[k] for k in exp} == exp
        assert got["line"] and got["question"]["id"] == exp["question_id"]
    assert out["score"] == sum(e["is_correct"] for e in expected)
    assert out["passed"] is (out["score"] == out["total"])
    assert out["mood"] == ("proud" if out["passed"] else "confused")


def test_quiz_pass_records_round_and_streak(lsvc):
    teach(lsvc, FULL_LECTURE)
    out = lsvc.loop_quiz("s1")
    assert out["passed"] and out["mood"] == "proud" and out["streak"] == 1
    assert out["result_line"] == persona.result_line(3, 3)
    rounds = lsvc.repo.list_rounds("s1")
    assert rounds[0]["id"] == out["round_id"] and rounds[0]["passed"] is True
    assert rounds[0]["created_at"] == "2026-10-17T09:30:00"
    assert lsvc.loop_today("s1")["mood"] == "proud"


def test_streak_math():
    d = date(2026, 10, 17)
    days = {d, d - timedelta(1), d - timedelta(2), d - timedelta(5), d - timedelta(6), d - timedelta(7), d - timedelta(8)}
    assert current_streak(days, d) == 3
    assert current_streak(days, d + timedelta(1)) == 3  # yesterday still counts
    assert current_streak(days, d + timedelta(2)) == 0
    assert current_streak(set(), d) == 0
    assert best_streak(days) == 4 and best_streak(set()) == 0


def test_today_streak_with_clock(lsvc, clock):
    teach(lsvc, FULL_LECTURE)
    t0 = lsvc.loop_today("s1")
    assert t0["streak"] == 0 and t0["mood"] == "listening" and t0["last_round_at"] is None
    for _ in range(3):
        lsvc.loop_quiz("s1")
        clock.advance(1)
    today = lsvc.loop_today("s1")  # no round yet today, yesterday keeps it alive
    assert today["streak"] == 3 and today["best_streak"] == 3 and today["days_since_last"] == 1
    assert today["mood"] == "listening"
    clock.advance(2)
    later = lsvc.loop_today("s1")
    assert later["streak"] == 0 and later["best_streak"] == 3 and later["mood"] == "sad"
    assert later["days_since_last"] == 3


def test_today_confused_after_failed_round(lsvc):
    teach(lsvc, "A function can call itself.")
    assert not lsvc.loop_quiz("s1")["passed"]
    assert lsvc.loop_today("s1")["mood"] == "confused"


def test_today_ask_picks_misconception_before_missing(lsvc):
    t = lsvc.loop_today("s1")
    assert t["ask"] == {"concept_id": "self_call", "label": "Self call", "reason": "missing"}
    teach(lsvc, "A function can call itself. Only the last call's return value matters.")
    t = lsvc.loop_today("s1")
    assert t["ask"] == {"concept_id": "return_propagation", "label": "Return propagation", "reason": "misconception"}
    assert t["progress"] == {"mastered": 1, "total": 5} and t["level"] == "Freshman"
    assert "return propagation" in t["line"]


def test_today_review_when_all_mastered(lsvc):
    teach(lsvc, FULL_LECTURE)
    t = lsvc.loop_today("s1")
    assert t["ask"]["reason"] == "review" and t["level"] == "Graduate"
    assert t["progress"] == {"mastered": 5, "total": 5}


def test_levels():
    assert [level_for(n) for n in range(6)] == ["Freshman", "Freshman", "Sophomore", "Junior", "Junior", "Graduate"]


def test_reset_clears_rounds(lsvc):
    teach(lsvc, FULL_LECTURE)
    lsvc.loop_quiz("s1")
    lsvc.loop_quiz("s2")
    lsvc.repo.reset_session("s1")
    assert lsvc.repo.list_rounds("s1") == []
    assert len(lsvc.repo.list_rounds("s2")) == 1
    assert lsvc.loop_today("s1")["streak"] == 0


def test_persona_lines_are_deterministic(lsvc, key):
    teach(lsvc, "All the calls share the same variables.")
    q6 = next(q for q in lsvc.repo.list_questions() if q["id"] == "q6")
    r = grade_exam([q6], lsvc.active_notebook("s1"))[0]
    line = persona.quiz_line(r, q6, key)
    assert line == persona.quiz_line(r, q6, key)
    assert "All the calls share the same variables" in line and "“True”" in line
    nt = persona.quiz_line(grade_exam([q6], {})[0], q6, key)
    assert "independent frames" in nt
    assert persona.result_line(2, 3) == persona.result_line(2, 3)
    assert persona.absent_line(3) == persona.absent_line(3) and "3" in persona.absent_line(3)
    g = persona.greeting("sad", 0, "Base case", days_missed=2)
    assert g == persona.greeting("sad", 0, "Base case", days_missed=2) and "base case" in g


def test_persona_lines_have_no_dash_punctuation(key, questions):
    lines = [persona.result_line(s, 3) for s in range(4)] + [persona.absent_line(d) for d in range(5)]
    lines += [persona.greeting(m, s, "Base case", 2) for m in ("listening", "proud", "confused", "sad") for s in range(4)]
    for q in questions:
        lines.append(persona.quiz_line(grade_exam([q], {})[0], q, key))
    for line in lines:
        assert " - " not in line and "—" not in line and "–" not in line, line


def test_loop_endpoints(monkeypatch, lsvc):
    import app.repo.base
    import app.speech.base
    monkeypatch.setattr(app.speech.base, "get_speech_client", lambda _p: lsvc.speech)
    monkeypatch.setattr(app.repo.base, "get_repository", lambda _p: lsvc.repo)
    from app import main
    monkeypatch.setattr(main, "svc", lsvc)
    client = TestClient(main.app)
    h = {"X-Session-Id": "api"}
    quiz = client.post("/loop/quiz", headers=h).json()
    assert {"round_id", "score", "total", "passed", "mood", "result_line", "results", "streak"} <= set(quiz)
    today = client.get("/loop/today", headers=h).json()
    assert {"streak", "best_streak", "last_round_at", "days_since_last", "mood", "ask", "line",
            "progress", "level"} <= set(today)
    assert client.post("/session/reset", headers=h).json() == {"ok": True}
    assert client.get("/loop/today", headers=h).json()["last_round_at"] is None
