"""Offline stand-in for the live exam: questions and answers built from the notes by word overlap. The demo safety net."""
import re
from collections.abc import Iterator

from .base import LLMClient

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
    # Live exam, offline: one question per notes sentence, answered by the transcript sentence sharing the most words.
    def __init__(self):
        self._refs: dict[str, str] = {}  # question prompt -> notes sentence it was written from

    def generate_questions(self, n: int, notes: str) -> list[dict]:
        out = []
        for s in _sentences(notes):
            if len(s.split()) < 6:
                continue
            prompt = f"Explain what the notes say about: {' '.join(s.split()[:4])}..."
            self._refs[prompt] = s
            out.append({"prompt": prompt, "reference_answer": s})
            if len(out) == n:
                break
        if not out:
            raise ValueError("no usable sentences in the notes")
        return out

    def answer_stream(self, question: str, transcripts: str) -> Iterator[str]:
        ref = self._refs.get(question)
        sentences = _sentences(transcripts)
        if ref:
            best = max(sentences, key=lambda s: _overlap(s, ref), default=None)
            hits = [best] if best and _overlap(best, ref) >= _MIN_OVERLAP else []
        else:
            hits = []
        reply = (f"You told me: {hits[-1]}\nQUOTE: {hits[-1]}" if hits  # latest teaching wins
                 else "I don't know. You never taught me that.\nQUOTE: NONE")
        for i in range(0, len(reply), 12):
            yield reply[i:i + 12]

    def judge(self, question: str, reference: str, answer: str, quote: str) -> dict:
        # the mock only ever answers by quoting a sentence, so its answers are always supported by the quote
        if question in self._refs and _overlap(answer, self._refs[question]) >= _MIN_OVERLAP:
            return {"is_correct": True, "supported": True, "feedback": "That matches the notes."}
        return {"is_correct": False, "supported": True, "feedback": "That does not cover the key idea."}
