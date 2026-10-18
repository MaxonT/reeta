from datetime import date

from app import gradebook


def attempt(no, results, created_at="2026-10-18 10:00:00", **answer_extra):
    return {"attempt_no": no, "created_at": created_at, "answers": [
        {"question_id": f"q{i}", "prompt": f"P{i}", "is_correct": r == "correct", "reason": r,
         "feedback": f"f{i}", **answer_extra} for i, r in enumerate(results, 1)]}


def test_attempt_without_answers_is_not_a_grade():
    assert gradebook.attempt_grades({"attempt_no": 1, "created_at": "2026-10-18 10:00:00", "answers": []}, 1.0) is None
    assert gradebook.gradebook([{"attempt_no": 1, "created_at": "x", "answers": []}], 1.0) == []


def test_score_is_counted_from_answers_and_pass_uses_threshold():
    row = gradebook.attempt_grades(attempt(1, ["correct", "correct", "wrong"]), 1.0)
    assert (row["score"], row["total"], row["percent"], row["passed"]) == (2, 3, 67, False)
    assert gradebook.attempt_grades(attempt(1, ["correct", "correct", "wrong"]), 0.6)["passed"] is True
    assert gradebook.attempt_grades(attempt(1, ["correct"]), 1.0)["passed"] is True


def test_rows_carry_grades_only():
    row = gradebook.attempt_grades(attempt(1, ["wrong"], answer="secret", quote="from recording", line="said",
                                           lecture_id=4, quote_start_ms=0, quote_end_ms=10), 1.0)
    assert set(row) == {"attempt_no", "created_at", "score", "total", "percent", "passed", "questions"}
    assert row["questions"] == [{"question_id": "q1", "prompt": "P1", "result": "wrong", "feedback": "f1"}]


def test_missing_prompt_and_feedback_become_empty_strings():
    at = {"attempt_no": 1, "created_at": "2026-10-18 10:00:00",
          "answers": [{"question_id": "q1", "prompt": None, "is_correct": False, "reason": "not_taught",
                       "feedback": None}]}
    assert gradebook.attempt_grades(at, 1.0)["questions"][0] == {"question_id": "q1", "prompt": "",
                                                                 "result": "not_taught", "feedback": ""}


def test_summary_of_nothing():
    s = gradebook.summary([])
    assert s["quizzes"] == 0 and s["last"] is None and s["streak"] == 0 and s["average_percent"] is None


def test_summary_numbers():
    rows = gradebook.gradebook([
        attempt(1, ["correct", "wrong", "not_taught"], "2026-10-16 09:00:00"),
        attempt(2, ["correct", "correct", "correct"], "2026-10-17 09:00:00"),
        attempt(3, ["correct", "not_taught"], "2026-10-18 09:00:00"),
    ], 1.0)
    s = gradebook.summary(rows, today=date(2026, 10, 18))
    assert s["quizzes"] == 3 and s["passes"] == 1
    assert s["last"] == {"score": 1, "total": 2, "percent": 50, "passed": False, "created_at": "2026-10-18 09:00:00"}
    assert s["best_percent"] == 100
    assert s["average_percent"] == round(100 * (1 / 3 + 1 + 1 / 2) / 3)  # 61, from raw scores not rounded percents
    assert (s["wrong"], s["not_taught"]) == (1, 2)
    assert s["last_active"] == "2026-10-18 09:00:00"
    assert s["streak"] == 1  # passed yesterday, not yet today


def test_streak_rules():
    d = date(2026, 10, 18)
    days = lambda *offsets: {date.fromordinal(d.toordinal() - o) for o in offsets}  # noqa: E731
    assert gradebook.streak(set(), d) == 0
    assert gradebook.streak(days(0, 1, 2), d) == 3
    assert gradebook.streak(days(1, 2), d) == 2   # not passed yet today, still alive
    assert gradebook.streak(days(2, 3), d) == 0   # missed yesterday
    assert gradebook.streak(days(0, 2, 3), d) == 1


def test_two_passes_on_one_day_count_once():
    rows = gradebook.gradebook([attempt(1, ["correct"], "2026-10-18 09:00:00"),
                                attempt(2, ["correct"], "2026-10-18 17:00:00")], 1.0)
    assert gradebook.summary(rows, today=date(2026, 10, 18))["streak"] == 1


def test_topic_progress_status():
    rows = lambda *results: gradebook.gradebook([attempt(i, r) for i, r in enumerate(results, 1)], 1.0)  # noqa: E731
    assert gradebook.topic_progress([], taught=False)["status"] == "not_started"
    assert gradebook.topic_progress([], taught=True)["status"] == "practicing"
    assert gradebook.topic_progress(rows(["wrong"]), taught=False)["status"] == "practicing"
    p = gradebook.topic_progress(rows(["wrong"], ["correct"], ["wrong"]), taught=True)
    assert p["status"] == "passed"  # passed once stays passed
    assert (p["quizzes"], p["best_percent"], p["last"]["score"]) == (3, 100, 0)
    assert p["first_passed_at"] == "2026-10-18 10:00:00"
    assert gradebook.topic_progress([], taught=False)["best_percent"] is None
