import json

from ..config import settings
from ..content import AnswerKey
from .base import LLMClient, template_phrase, validate_entries

EXTRACT_SYSTEM = """You label sentences from a Professor's spoken Lecture about {topic}.
For each sentence decide which Answer key concept it teaches, and whether it teaches it
correctly or states one of the listed misconceptions. Ignore sentences that teach none.
Judge ONLY what the sentence says. Do not fill gaps with your own knowledge.
A sentence that says the opposite of a misconception (e.g. "it does NOT stop by itself") is correct.
Return strict JSON: {{"entries": [{{"sentence_idx": int, "concept_id": str,
"status": "correct"|"misconception", "misconception_id": str|null}}]}}
Answer key:
{answer_key}"""

PHRASE_SYSTEM = """You are the AI student. You only know what your Professor taught you.
Rewrite the given result as one or two short first person sentences spoken to the Professor.
Keep the given answer exactly. Quote the Professor's sentence if one is given.
Never add facts, never explain beyond the notes, never correct the answer."""


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
        payload = {
            "question": question["prompt"],
            "my_answer": result["answer"] or "I don't know",
            "reason": result["reason"],
            "professor_said": [c["text"] for c in result["citations"]],
            "never_taught": [key.label(c) for c in result["missing_concepts"]],
            "template": template_phrase(result, question, key),
        }
        resp = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.7,
            max_tokens=80,
            messages=[{"role": "system", "content": PHRASE_SYSTEM},
                      {"role": "user", "content": json.dumps(payload)}],
        )
        return resp.choices[0].message.content.strip()
