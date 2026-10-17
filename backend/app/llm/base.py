"""LLMs are used for exactly two things:
  1. extract_entries: map Lecture sentences to Answer key concepts
  2. phrase: word the AI student's reply for an already graded result
They never decide an answer. Grading lives in grading.py.
"""
from abc import ABC, abstractmethod

from ..content import AnswerKey

VALID_STATUS = {"correct", "misconception"}


class LLMClient(ABC):
    @abstractmethod
    def extract_entries(self, sentences: list[dict], key: AnswerKey) -> list[dict]:
        """-> [{sentence_idx, concept_id, status, misconception_id}] (irrelevant sentences omitted)"""

    @abstractmethod
    def phrase(self, result: dict, question: dict, key: AnswerKey) -> str:
        """-> one or two sentences the AI student says about this graded result"""


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
