"""LLMs write the live exam's questions from the teacher's notes, answer them as Reeta from the lecture
transcripts, and judge the answers. Not abstract: a client without them falls through to the Mock in
FallbackLLMClient."""
from abc import ABC
from collections.abc import Iterator

RESET = "\x00reset"  # yielded by FallbackLLMClient.answer_stream when it restarts the answer on the fallback


class LLMClient(ABC):
    def generate_questions(self, n: int, notes: str) -> list[dict]:
        """-> [{prompt, reference_answer}] open-ended, written from `notes` (the session's source material)."""
        raise NotImplementedError

    def answer_stream(self, question: str, transcripts: str) -> Iterator[str]:
        """Yield raw text chunks of Reeta's reply: `<answer>\\nQUOTE: <verbatim words | NONE>`"""
        raise NotImplementedError

    def judge(self, question: str, reference: str, answer: str, quote: str) -> dict:
        """-> {is_correct: bool, supported: bool, feedback: str}. supported=False means the answer
        goes beyond what the quote says (outside knowledge), which counts as not taught."""
        raise NotImplementedError


class FallbackLLMClient(LLMClient):
    """Try the primary client, fall back to another (the Mock) on any error."""

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self.primary, self.fallback = primary, fallback

    def generate_questions(self, n, notes):
        try:
            return self.primary.generate_questions(n, notes)
        except Exception as exc:  # noqa: BLE001 demo safety net
            print(f"[llm] primary generate_questions failed, using fallback: {exc}")
            return self.fallback.generate_questions(n, notes)

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
    raise ValueError(f"unknown LLM_PROVIDER {provider!r}")
