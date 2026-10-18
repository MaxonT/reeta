import json
from collections.abc import Iterator

from ..config import settings
from ..content import AnswerKey
from ..persona import PERSONA_PROMPT
from .base import LLMClient, checked_phrase, phrase_payload, validate_entries
from .exam_prompts import (JUDGE_SYSTEM, QUESTIONS_SYSTEM, REETA_SYSTEM, extract_json, notes_text,
                           validate_questions)

EXTRACT_SYSTEM = """You label sentences from a Professor's spoken Lecture about {topic}.
For each sentence decide which Answer key concept it teaches, and whether it teaches it
correctly or states one of the listed misconceptions. Ignore sentences that teach none.
Judge ONLY what the sentence says. Do not fill gaps with your own knowledge.
A sentence that says the opposite of a misconception (e.g. "it does NOT stop by itself") is correct.
Return strict JSON: {{"entries": [{{"sentence_idx": int, "concept_id": str,
"status": "correct"|"misconception", "misconception_id": str|null}}]}}
Answer key:
{answer_key}"""

PHRASE_SYSTEM = PERSONA_PROMPT + """
You get the graded result as JSON. Rewrite it as Reeta speaking to the Professor.
The "template" field is a sample line in your voice; you may reuse it."""


class OpenAIClient(LLMClient):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.openai_api_key or None, timeout=20)

    def extract_entries(self, sentences: list[dict], key: AnswerKey) -> list[dict]:
        compact_key = [
            {"id": c["id"], "description": c["description"],
             "misconceptions": [{"id": m["id"], "description": m["description"]} for m in c["misconceptions"]]}
            for c in key.concepts
        ]
        resp = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM.format(topic=key.topic, answer_key=json.dumps(compact_key))},
                {"role": "user", "content": json.dumps([{"idx": s["idx"], "text": s["text"]} for s in sentences])},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return validate_entries(data.get("entries", []), sentences, key)

    def phrase(self, result: dict, question: dict, key: AnswerKey) -> str:
        payload = phrase_payload(result, question, key)
        resp = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.7,
            max_tokens=120,
            messages=[{"role": "system", "content": PHRASE_SYSTEM},
                      {"role": "user", "content": json.dumps(payload)}],
        )
        return checked_phrase(resp.choices[0].message.content, result, question, key)

    # Live exam
    def _chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        resp = self.client.chat.completions.create(
            model=settings.openai_model, temperature=temperature, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return (resp.choices[0].message.content or "").strip()

    def generate_questions(self, key: AnswerKey, n: int, notes: str | None = None) -> list[dict]:
        topic, notes = (key.topic, notes_text(key)) if notes is None else ("the uploaded material", notes)
        text = self._chat(QUESTIONS_SYSTEM.format(topic=topic, n=n, notes=notes),
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
