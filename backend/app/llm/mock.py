"""Offline extractor: synonym and misconception phrase matching. The demo safety net."""
import re
from collections.abc import Iterator

from ..content import AnswerKey
from ..persona import quiz_line
from .base import LLMClient, validate_entries

_NEGATION = re.compile(r"\b(not|never|no|don't|dont|doesn't|doesnt|isn't|isnt|aren't|won't|can't|cannot)\b")


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9'\- ]", " ", text)).strip()


def _find(text: str, phrase: str) -> int:
    m = re.search(r"(?<![a-z0-9])" + re.escape(_norm(phrase)) + r"(?![a-z0-9])", text)
    return m.start() if m else -1


def _negated(text: str, pos: int) -> bool:
    """A negation within the 4 words before the match flips its meaning."""
    window = " ".join(text[:pos].split()[-4:])
    return bool(_NEGATION.search(window))


_MIN_OVERLAP = 0.5  # share of the reference's words that must appear in the answer / transcript sentence


def _sentences(text: str) -> list[str]:
    """Sentences of a transcript or notes block, skipping the '[Lecture 1]' and '## file' labels."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith(("[Lecture", "## "))]
    return [s.strip() for ln in lines for s in re.split(r"(?<=[.!?])\s+", ln) if s.strip()]


def _overlap(text: str, ref: str) -> float:
    """Share of the reference's longer words (4+ letters) that also appear in text."""
    words = {w for w in _norm(ref).split() if len(w) >= 4}
    have = set(_norm(text).split())
    return len(words & have) / len(words) if words else 0.0


class MockLLMClient(LLMClient):
    def extract_entries(self, sentences: list[dict], key: AnswerKey) -> list[dict]:
        raw = []
        for s in sentences:
            text = _norm(s["text"])
            for concept in key.concepts:
                entry = self._match_concept(text, concept)
                if entry:
                    raw.append({"sentence_idx": s["idx"], "concept_id": concept["id"], **entry})
        return validate_entries(raw, sentences, key)

    @staticmethod
    def _match_concept(text: str, concept: dict) -> dict | None:
        for m in concept.get("misconceptions", []):
            for phrase in m["phrases"]:
                pos = _find(text, phrase)
                if pos >= 0:
                    if _negated(text, pos):  # "it does NOT stop by itself" is a correct statement
                        return {"status": "correct", "misconception_id": None}
                    return {"status": "misconception", "misconception_id": m["id"]}
        for syn in concept.get("synonyms", []):
            if _find(text, syn) >= 0:
                return {"status": "correct", "misconception_id": None}
        return None

    def phrase(self, result: dict, question: dict, key: AnswerKey) -> str:
        return quiz_line(result, question, key)
