import json
from collections.abc import Iterator

from ..config import settings
from .base import LLMClient
from .exam_prompts import JUDGE_SYSTEM, QUESTIONS_SYSTEM, REETA_SYSTEM, extract_json, validate_questions


class OpenAIClient(LLMClient):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.openai_api_key or None, timeout=20)

    # Live exam
    def _chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        resp = self.client.chat.completions.create(
            model=settings.openai_model, temperature=temperature, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return (resp.choices[0].message.content or "").strip()

    def generate_questions(self, n: int, notes: str) -> list[dict]:
        text = self._chat(QUESTIONS_SYSTEM.format(topic="the uploaded material", n=n, notes=notes),
                          f"Write the {n} questions.", temperature=0.7, max_tokens=1200)
        return validate_questions(extract_json(text).get("questions"), n)

    def answer_stream(self, question: str, transcripts: str) -> Iterator[str]:
        user = f"Transcripts:\n{transcripts or '(the Professor has not taught you anything yet)'}\n\nQuestion: {question}"
        stream = self.client.chat.completions.create(
            model=settings.openai_model, temperature=0.3, max_tokens=250, stream=True,
            messages=[{"role": "system", "content": REETA_SYSTEM}, {"role": "user", "content": user}])
        for event in stream:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content

    def judge(self, question: str, reference: str, answer: str, quote: str) -> dict:
        text = self._chat(JUDGE_SYSTEM, json.dumps({"question": question, "reference_answer": reference,
                                                    "student_answer": answer, "professor_quote": quote}),
                          temperature=0, max_tokens=120)
        data = extract_json(text)
        verdict = data.get("verdict")
        return {"is_correct": verdict == "correct", "supported": verdict != "unsupported",
                "feedback": str(data.get("feedback", "")).strip()}
