"""Gradebook: a student's exam attempts as scores. Pure functions over repo.list_attempts().

Teachers see grades only: each question's prompt, result and the judge's one line. Never Reeta's answer, the
quote from the student's lecture, or anything that points at the recording.
"""
from datetime import date, datetime, timedelta, timezone


def attempt_grades(attempt: dict, pass_threshold: float) -> dict | None:
    """One gradebook row, or None for an attempt that never got an answer (the exam failed to start)."""
    answers = attempt.get("answers") or []
    if not answers:
        return None
    score = sum(1 for a in answers if a["is_correct"])  # counted, so an interrupted attempt still adds up
    total = len(answers)
    return {
        "attempt_no": attempt["attempt_no"],
        "created_at": attempt["created_at"],
        "score": score,
        "total": total,
        "percent": round(100 * score / total),
        "passed": score >= pass_threshold * total,
        "questions": [{"question_id": a["question_id"], "prompt": a.get("prompt") or "",
                       "result": a["reason"], "feedback": a.get("feedback") or ""} for a in answers],
    }


def gradebook(attempts: list[dict], pass_threshold: float) -> list[dict]:
    """Rows oldest first."""
    return [row for at in attempts if (row := attempt_grades(at, pass_threshold))]


def summary(rows: list[dict], today: date | None = None) -> dict:
    """Headline numbers for a roster row, from gradebook() rows."""
    if not rows:
        return {"quizzes": 0, "last": None, "best_percent": None, "average_percent": None, "passes": 0,
                "last_active": None, "streak": 0, "wrong": 0, "not_taught": 0}
    last = rows[-1]
    results = [q["result"] for r in rows for q in r["questions"]]
    return {
        "quizzes": len(rows),
        "last": {k: last[k] for k in ("score", "total", "percent", "passed", "created_at")},
        "best_percent": max(r["percent"] for r in rows),
        "average_percent": round(100 * sum(r["score"] / r["total"] for r in rows) / len(rows)),
        "passes": sum(r["passed"] for r in rows),
        "last_active": last["created_at"],
        "streak": streak({_day(r["created_at"]) for r in rows if r["passed"]}, today),
        "wrong": results.count("wrong"),            # taught it, but taught it wrong
        "not_taught": results.count("not_taught"),  # never taught it
    }


def topic_progress(rows: list[dict], taught: bool) -> dict:
    """Where a student is on one topic: not_started (nothing taught, no quiz), practicing, or passed."""
    passed = [r for r in rows if r["passed"]]
    status = "passed" if passed else "practicing" if rows or taught else "not_started"
    return {"status": status, "quizzes": len(rows),
            "best_percent": max((r["percent"] for r in rows), default=None),
            "last": {k: rows[-1][k] for k in ("score", "total", "percent", "passed", "created_at")} if rows else None,
            "first_passed_at": passed[0]["created_at"] if passed else None}


def streak(pass_days: set[date], today: date | None = None) -> int:
    """Consecutive days with a pass, ending today or yesterday (same rule as the frontend's loopState)."""
    today = today or datetime.now(timezone.utc).date()
    day = today if today in pass_days else today - timedelta(days=1)
    n = 0
    while day in pass_days:
        n += 1
        day -= timedelta(days=1)
    return n


def _day(created_at: str) -> date:
    return date.fromisoformat(str(created_at)[:10])  # 'YYYY-MM-DD HH:MM:SS', UTC
