"""Answer key and Exam loaded from content/*.json, with validation."""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AnswerKey:
    topic: str
    concepts: list[dict]
    concept_ids: list[str] = field(default_factory=list)
    misconception_ids: dict[str, str] = field(default_factory=dict)  # misconception_id -> concept_id
    edges: list[tuple[str, str]] = field(default_factory=list)  # (source, target) concept ids

    def concept(self, concept_id: str) -> dict:
        return next(c for c in self.concepts if c["id"] == concept_id)

    def label(self, concept_id: str) -> str:
        return self.concept(concept_id)["label"]

    def misconception(self, misconception_id: str) -> dict | None:
        for c in self.concepts:
            for m in c.get("misconceptions", []):
                if m["id"] == misconception_id:
                    return m
        return None


def load_answer_key(content_dir: Path) -> AnswerKey:
    data = json.loads((content_dir / "answer_key.json").read_text())
    key = AnswerKey(topic=data["topic"], concepts=data["concepts"])
    key.concept_ids = [c["id"] for c in key.concepts]
    for c in key.concepts:
        for m in c.get("misconceptions", []):
            key.misconception_ids[m["id"]] = c["id"]
    for s, t in data.get("edges", []):
        assert s in key.concept_ids and t in key.concept_ids, f"edge {s}->{t}: unknown concept"
        key.edges.append((s, t))
    return key


def load_exam(content_dir: Path, key: AnswerKey) -> list[dict]:
    questions = json.loads((content_dir / "exam.json").read_text())["questions"]
    for q in questions:
        assert q["correct_answer"] in q["options"], f"{q['id']}: correct_answer not in options"
        for cid in q["required_concepts"]:
            assert cid in key.concept_ids, f"{q['id']}: unknown concept {cid}"
        for mid, opt in q.get("distractor_map", {}).items():
            assert mid in key.misconception_ids, f"{q['id']}: unknown misconception {mid}"
            assert opt in q["options"], f"{q['id']}: distractor {opt!r} not in options"
    return questions
