"""Grading rules: misconception > not taught > correct. Pure code, no LLM."""
from app.grading import grade_question


def entry(eid, concept_id, status="correct", misconception_id=None, text="sentence"):
    return {"id": eid, "concept_id": concept_id, "status": status, "misconception_id": misconception_id,
            "sentence": {"id": eid * 10, "lecture_id": 1, "text": text, "start_ms": 100 * eid, "end_ms": 100 * eid + 90}}


Q = {
    "id": "q8", "type": "mcq", "prompt": "sum_to(3)?",
    "options": ["6", "0", "3", "It never returns"], "correct_answer": "6",
    "required_concepts": ["base_case", "smaller_problem", "return_propagation"],
    "distractor_map": {"return_only_last": "0", "base_case_stops_itself": "It never returns"},
}


def test_all_taught_correctly_answers_correctly_and_cites_entries():
    nb = {"base_case": entry(1, "base_case"), "smaller_problem": entry(2, "smaller_problem"),
          "return_propagation": entry(3, "return_propagation")}
    r = grade_question(Q, nb)
    assert r["is_correct"] and r["reason"] == "correct" and r["answer"] == "6"
    assert r["concept_ids"] == Q["required_concepts"]
    assert r["sentence_ids"] == [10, 20, 30]
    assert r["citations"][0]["start_ms"] == 100 and r["citations"][0]["end_ms"] == 190


def test_missing_concept_is_not_taught_and_named():
    nb = {"base_case": entry(1, "base_case"), "smaller_problem": entry(2, "smaller_problem")}
    r = grade_question(Q, nb)
    assert not r["is_correct"]
    assert r["reason"] == "not_taught"
    assert r["answer"] is None
    assert r["missing_concepts"] == ["return_propagation"]
    assert r["concept_ids"] == ["return_propagation"]
    assert r["sentence_ids"] == []


def test_empty_notebook_names_every_concept():
    r = grade_question(Q, {})
    assert r["reason"] == "not_taught" and r["missing_concepts"] == Q["required_concepts"]


def test_misconception_picks_mapped_distractor_and_cites_sentence():
    nb = {"base_case": entry(1, "base_case"), "smaller_problem": entry(2, "smaller_problem"),
          "return_propagation": entry(3, "return_propagation", "misconception", "return_only_last",
                                      text="Only the last call's return matters.")}
    r = grade_question(Q, nb)
    assert not r["is_correct"]
    assert r["reason"] == "misconception"
    assert r["answer"] == "0"
    assert r["concept_ids"] == ["return_propagation"]
    assert r["sentence_ids"] == [30]
    assert r["citations"][0]["text"] == "Only the last call's return matters."


def test_misconception_beats_missing():
    nb = {"base_case": entry(1, "base_case", "misconception", "base_case_stops_itself")}
    r = grade_question(Q, nb)
    assert r["reason"] == "misconception"
    assert r["answer"] == "It never returns"


def test_misconception_without_mapping_still_answers_wrong():
    nb = {"base_case": entry(1, "base_case", "misconception", None), "smaller_problem": entry(2, "smaller_problem"),
          "return_propagation": entry(3, "return_propagation")}
    r = grade_question(Q, nb)
    assert not r["is_correct"] and r["answer"] != Q["correct_answer"] and r["answer"] in Q["options"]


def test_every_exam_question_is_consistent(questions):
    for q in questions:
        assert grade_question(q, {})["reason"] == "not_taught"
