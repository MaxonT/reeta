"""OCI Generative AI client (Cohere chat model, on-demand serving).

Needs OCI_COMPARTMENT_ID and OCI_GENAI_MODEL_ID in .env, plus ~/.oci/config.
get_llm_client("oci") wraps this in FallbackLLMClient, so the Mock answers on any error.
"""
import json
import re
from collections.abc import Iterator

from ..config import settings
from ..content import AnswerKey
from .base import LLMClient, template_phrase, validate_entries
from .exam_prompts import (JUDGE_SYSTEM, QUESTIONS_SYSTEM, REETA_SYSTEM, extract_json, notes_text,
                           validate_questions)
from .openai_client import EXTRACT_SYSTEM, PHRASE_SYSTEM


class OCIGenAIClient(LLMClient):
    def __init__(self):
        import oci
        config = oci.config.from_file(settings.oci_config_file, settings.oci_profile)
        endpoint = f"https://inference.generativeai.{settings.oci_region}.oci.oraclecloud.com"
        self.models = oci.generative_ai_inference.models
        self.client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=config, service_endpoint=endpoint,
            retry_strategy=oci.retry.NoneRetryStrategy(), timeout=(10, 30))

    def _details(self, system: str, user: str, temperature: float, max_tokens: int, stream: bool = False):
        req = self.models.CohereChatRequest(
            message=user, preamble_override=system,
            temperature=temperature, max_tokens=max_tokens, is_stream=stream)
        return self.models.ChatDetails(
            compartment_id=settings.oci_compartment_id,
            serving_mode=self.models.OnDemandServingMode(model_id=settings.oci_genai_model_id),
            chat_request=req)

    def _chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        detail = self._details(system, user, temperature, max_tokens)
        return self.client.chat(detail).data.chat_response.text.strip()

    def _stream(self, system: str, user: str, temperature: float, max_tokens: int) -> Iterator[str]:
        resp = self.client.chat(self._details(system, user, temperature, max_tokens, stream=True))
        for event in resp.data.events():
            data = json.loads(event.data)
            if data.get("finishReason"):  # the last event repeats the whole text, skip it
                break
            if data.get("text"):
                yield data["text"]

    def extract_entries(self, sentences: list[dict], key: AnswerKey) -> list[dict]:
        compact_key = [
            {"id": c["id"], "description": c["description"],
             "misconceptions": [{"id": m["id"], "description": m["description"]} for m in c["misconceptions"]]}
            for c in key.concepts
        ]
        text = self._chat(
            EXTRACT_SYSTEM.format(topic=key.topic, answer_key=json.dumps(compact_key)),
            json.dumps([{"idx": s["idx"], "text": s["text"]} for s in sentences]),
            temperature=0, max_tokens=1500)
        match = re.search(r"\{.*\}", text, re.DOTALL)  # model may wrap JSON in prose or fences
        data = json.loads(match.group(0) if match else text)
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
        return self._chat(PHRASE_SYSTEM, json.dumps(payload), temperature=0.7, max_tokens=80)

    # Live exam
    def generate_questions(self, key: AnswerKey, n: int, notes: str | None = None) -> list[dict]:
        topic, notes = (key.topic, notes_text(key)) if notes is None else ("the uploaded material", notes)
        text = self._chat(QUESTIONS_SYSTEM.format(topic=topic, n=n, notes=notes),
                          f"Write the {n} questions.", temperature=0.7, max_tokens=1200)
        return validate_questions(extract_json(text).get("questions"), n)

    def answer_stream(self, question: str, transcripts: str) -> Iterator[str]:
        user = f"Transcripts:\n{transcripts or '(the Professor has not taught you anything yet)'}\n\nQuestion: {question}"
        yield from self._stream(REETA_SYSTEM, user, temperature=0.3, max_tokens=250)

    def judge(self, question: str, reference: str, answer: str, quote: str) -> dict:
        text = self._chat(JUDGE_SYSTEM, json.dumps({"question": question, "reference_answer": reference,
                                                    "student_answer": answer, "professor_quote": quote}),
                          temperature=0, max_tokens=120)
        data = extract_json(text)
        verdict = data.get("verdict")
        return {"is_correct": verdict == "correct", "supported": verdict != "unsupported",
                "feedback": str(data.get("feedback", "")).strip()}
