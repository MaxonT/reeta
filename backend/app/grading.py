"""Deterministic Exam grading over the Notebook. No LLM is involved here.

The AI student only knows what the latest confirmed Notebook entry says for each
concept. For every question:
  1. any required concept holds a misconception -> WRONG, answer the distractor
     mapped to that misconception, cite the Professor's sentence
  2. else any required concept is missing        -> WRONG ("never taught"),
     name the missing concepts
  3. else                                        -> CORRECT, cite the entries used
"""

MISCONCEPTION = "misconception"
NOT_TAUGHT = "not_taught"
CORRECT = "correct"


def _citation(entry: dict) -> dict:
    s = entry["sentence"]
    return {
        "entry_id": entry["id"],
        "concept_id": entry["concept_id"],
        "status": entry["status"],
        "misconception_id": entry.get("misconception_id"),
        "sentence_id": s["id"],
        "lecture_id": s["lecture_id"],
        "text": s["text"],
        "start_ms": s["start_ms"],
        "end_ms": s["end_ms"],
    }


def _wrong_option(question: dict, misconception_id: str | None) -> str:
    mapped = question.get("distractor_map", {}).get(misconception_id or "")
    if mapped:
        return mapped
    return next(o for o in question["options"] if o != question["correct_answer"])


def grade_question(question: dict, notebook: dict[str, dict]) -> dict:
    """notebook: concept_id -> latest confirmed entry (with joined sentence)."""
    required = question["required_concepts"]
    entries = [notebook.get(cid) for cid in required]

    wrong = [e for e in entries if e and e["status"] == MISCONCEPTION]
    if wrong:
        first = wrong[0]
        return {
            "question_id": question["id"],
            "answer": _wrong_option(question, first.get("misconception_id")),
            "is_correct": False,
            "reason": MISCONCEPTION,
            "concept_ids": [e["concept_id"] for e in wrong],
            "misconception_ids": [e.get("misconception_id") for e in wrong],
            "missing_concepts": [],
            "citations": [_citation(e) for e in wrong],
            "sentence_ids": [e["sentence"]["id"] for e in wrong],
        }

    missing = [cid for cid, e in zip(required, entries) if e is None]
    if missing:
        return {
            "question_id": question["id"],
            "answer": None,
            "is_correct": False,
            "reason": NOT_TAUGHT,
            "concept_ids": missing,
            "misconception_ids": [],
            "missing_concepts": missing,
            "citations": [],
            "sentence_ids": [],
        }

    return {
        "question_id": question["id"],
        "answer": question["correct_answer"],
        "is_correct": True,
        "reason": CORRECT,
        "concept_ids": list(required),
        "misconception_ids": [],
        "missing_concepts": [],
        "citations": [_citation(e) for e in entries],
        "sentence_ids": [e["sentence"]["id"] for e in entries],
    }


def grade_exam(questions: list[dict], notebook: dict[str, dict]) -> list[dict]:
    return [grade_question(q, notebook) for q in questions]


def concept_status(notebook: dict[str, dict], concept_id: str) -> str:
    """correct | misconception | missing"""
    e = notebook.get(concept_id)
    return e["status"] if e else "missing"
