"""LLMs are used for exactly two things:
  1. extract_entries: map Lecture sentences to Answer key concepts
  2. phrase: word the AI student's reply for an already graded result
They never decide an answer. Grading lives in grading.py.
"""
from abc import ABC, abstractmethod
from collections.abc import Iterator

from ..content import AnswerKey

VALID_STATUS = {"correct", "misconception"}
RESET = "\x00reset"  # yielded by FallbackLLMClient.answer_stream when it restarts the answer on the fallback


class LLMClient(ABC):
    @abstractmethod
    def extract_entries(self, sentences: list[dict], key: AnswerKey) -> list[dict]:
        """-> [{sentence_idx, concept_id, status, misconception_id}] (irrelevant sentences omitted)"""

    @abstractmethod
    def phrase(self, result: dict, question: dict, key: AnswerKey) -> str:
        """-> one or two sentences the AI student says about this graded result"""

    # Live exam. Not abstract: a client without them falls through to the Mock in FallbackLLMClient.
    def generate_questions(self, key: AnswerKey, n: int, notes: str | None = None) -> list[dict]:
        """-> [{prompt, reference_answer}] open-ended. Written from `notes` (the session's uploaded
        source material), or from the built-in course notes in `key` when notes is None."""
        raise NotImplementedError

    def answer_stream(self, question: str, transcripts: str) -> Iterator[str]:
        """Yield raw text chunks of Reeta's reply: `<answer>\\nQUOTE: <verbatim words | NONE>`"""
        raise NotImplementedError

    def judge(self, question: str, reference: str, answer: str, quote: str) -> dict:
        """-> {is_correct: bool, supported: bool, feedback: str}. supported=False means the answer
        goes beyond what the quote says (outside knowledge), which counts as not taught."""
        raise NotImplementedError


def validate_entries(raw: list, sentences: list[dict], key: AnswerKey) -> list[dict]:
    """Keep only entries whose ids exist in the Answer key. Strict, never trust the LLM."""
    valid_idx = {s["idx"] for s in sentences}
    out, seen = [], set()
    for e in raw if isinstance(raw, list) else []:
        if not isinstance(e, dict):
            continue
        idx, cid, status = e.get("sentence_idx"), e.get("concept_id"), e.get("status")
        mid = e.get("misconception_id") or None
        if idx not in valid_idx or cid not in key.concept_ids or status not in VALID_STATUS:
            continue
        if status == "misconception":
            if mid is not None and key.misconception_ids.get(mid) != cid:
                mid = None
        else:
            mid = None
        if (idx, cid) in seen:
            continue
        seen.add((idx, cid))
        out.append({"sentence_idx": idx, "concept_id": cid, "status": status, "misconception_id": mid})
    return out


def template_phrase(result: dict, question: dict, key: AnswerKey) -> str:
    """Deterministic fallback line for the AI student."""
    if result["reason"] == "not_taught":
        labels = ", ".join(key.label(c).lower() for c in result["missing_concepts"])
        return f"I don't know. You never taught me about {labels}."
    quote = result["citations"][0]["text"] if result["citations"] else ""
    if result["reason"] == "misconception":
        return f"I'll go with “{result['answer']}”, because you told me “{quote}”"
    return f"“{result['answer']}”. You taught me “{quote}”"


class FallbackLLMClient(LLMClient):
    """Try the primary client, fall back to another (the Mock) on any error."""

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self.primary, self.fallback = primary, fallback

    def extract_entries(self, sentences, key):
        try:
            return self.primary.extract_entries(sentences, key)
        except Exception as exc:  # noqa: BLE001 demo safety net
            print(f"[llm] primary extract failed, using fallback: {exc}")
            return self.fallback.extract_entries(sentences, key)

    def phrase(self, result, question, key):
        try:
            return self.primary.phrase(result, question, key)
        except Exception as exc:  # noqa: BLE001
            print(f"[llm] primary phrase failed, using fallback: {exc}")
            return self.fallback.phrase(result, question, key)

    def generate_questions(self, key, n, notes=None):
        try:
            return self.primary.generate_questions(key, n, notes)
        except Exception as exc:  # noqa: BLE001
            print(f"[llm] primary generate_questions failed, using fallback: {exc}")
            return self.fallback.generate_questions(key, n, notes)

    def answer_stream(self, question, transcripts):
        started = False
        try:
            for chunk in self.primary.answer_stream(question, transcripts):
                started = True
                yield chunk
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[llm] primary answer_stream failed, using fallback: {exc}")
        if started:
            yield RESET  # the partial answer on screen is discarded
        yield from self.fallback.answer_stream(question, transcripts)

    def judge(self, question, reference, answer, quote):
        try:
            return self.primary.judge(question, reference, answer, quote)
        except Exception as exc:  # noqa: BLE001
            print(f"[llm] primary judge failed, using fallback: {exc}")
            return self.fallback.judge(question, reference, answer, quote)


def get_llm_client(provider: str) -> LLMClient:
    from .mock import MockLLMClient
    if provider == "mock":
        return MockLLMClient()
    if provider == "openai":
        from .openai_client import OpenAIClient
        return FallbackLLMClient(OpenAIClient(), MockLLMClient())
    if provider == "oci":
        from .oci_genai import OCIGenAIClient
        return FallbackLLMClient(OCIGenAIClient(), MockLLMClient())
    raise ValueError(f"unknown LLM_PROVIDER {provider!r}")
