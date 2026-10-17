"""OCI Generative AI client (us-chicago-1, Cohere Command A).

Uses the same prompts as openai_client.py and ALWAYS passes extraction output
through validate_entries(). The `oci` package is imported lazily so tests and
mock mode run without it.

Env: OCI_COMPARTMENT_ID (required), OCI_PROFILE (default DEFAULT),
OCI_CONFIG_FILE (default ~/.oci/config), OCI_GENAI_MODEL (default cohere.command-a-03-2025),
OCI_GENAI_ENDPOINT (default us-chicago-1 inference endpoint).
"""
import json
import os
import re

from ..content import AnswerKey
from .base import LLMClient, template_phrase, validate_entries
from .openai_client import EXTRACT_SYSTEM, PHRASE_SYSTEM

DEFAULT_MODEL = "cohere.command-a-03-2025"
DEFAULT_ENDPOINT = "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"


def parse_json_text(text: str) -> dict:
    """Parse JSON from model text, tolerating code fences or surrounding prose."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


class OCIGenAIClient(LLMClient):
    def __init__(self):
        import oci
        self.oci = oci
        config = oci.config.from_file(
            os.path.expanduser(os.getenv("OCI_CONFIG_FILE", "~/.oci/config")),
            os.getenv("OCI_PROFILE", "DEFAULT"),
        )
        self.compartment_id = os.getenv("OCI_COMPARTMENT_ID") or config.get("tenancy")
        self.model_id = os.getenv("OCI_GENAI_MODEL", DEFAULT_MODEL)
        self.client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config,
            service_endpoint=os.getenv("OCI_GENAI_ENDPOINT", DEFAULT_ENDPOINT),
            timeout=(10, 30),
        )

    def _chat(self, system: str, message: str, temperature: float, max_tokens: int, json_mode: bool) -> str:
        m = self.oci.generative_ai_inference.models
        kwargs = dict(message=message, preamble_override=system, temperature=temperature, max_tokens=max_tokens)
        if json_mode and hasattr(m, "CohereResponseJsonFormat"):
            kwargs["response_format"] = m.CohereResponseJsonFormat()
        details = m.ChatDetails(
            compartment_id=self.compartment_id,
            serving_mode=m.OnDemandServingMode(model_id=self.model_id),
            chat_request=m.CohereChatRequest(**kwargs),
        )
        resp = self.client.chat(details)
        return resp.data.chat_response.text

    def extract_entries(self, sentences: list[dict], key: AnswerKey) -> list[dict]:
        compact_key = [
            {"id": c["id"], "description": c["description"],
             "misconceptions": [{"id": m["id"], "description": m["description"]} for m in c["misconceptions"]]}
            for c in key.concepts
        ]
        text = self._chat(
            EXTRACT_SYSTEM.format(topic=key.topic, answer_key=json.dumps(compact_key)),
            json.dumps([{"idx": s["idx"], "text": s["text"]} for s in sentences]),
            temperature=0, max_tokens=2000, json_mode=True,
        )
        data = parse_json_text(text)
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
        text = self._chat(PHRASE_SYSTEM, json.dumps(payload), temperature=0.7, max_tokens=80, json_mode=False)
        return text.strip()
