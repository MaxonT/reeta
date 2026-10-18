"""OCI GenAI client with a fake `oci` module: no network, no real package needed."""
import json
import sys
import types
from types import SimpleNamespace

from app.llm.oci_genai import OCIGenAIClient, parse_json_text


def _fake_oci(monkeypatch, reply_text, captured):
    class Model:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    models = types.SimpleNamespace(
        ChatDetails=Model, OnDemandServingMode=Model, CohereChatRequest=Model,
        CohereResponseJsonFormat=Model,
    )

    class FakeClient:
        def __init__(self, config, service_endpoint, timeout):
            captured["endpoint"] = service_endpoint

        def chat(self, details):
            captured["details"] = details
            return SimpleNamespace(data=SimpleNamespace(chat_response=SimpleNamespace(text=reply_text)))

    oci = types.ModuleType("oci")
    oci.config = SimpleNamespace(from_file=lambda path, profile: {"tenancy": "ocid1.tenancy.x", "profile": profile})
    oci.generative_ai_inference = SimpleNamespace(GenerativeAiInferenceClient=FakeClient, models=models)
    monkeypatch.setitem(sys.modules, "oci", oci)
    monkeypatch.setenv("OCI_COMPARTMENT_ID", "ocid1.compartment.test")


def test_oci_extraction_is_validated(monkeypatch, key):
    cid = key.concepts[0]["id"]
    reply = "```json\n" + json.dumps({"entries": [
        {"sentence_idx": 0, "concept_id": cid, "status": "correct", "misconception_id": None},
        {"sentence_idx": 0, "concept_id": "made_up", "status": "correct", "misconception_id": None},
        {"sentence_idx": 9, "concept_id": cid, "status": "correct", "misconception_id": None},
    ]}) + "\n```"
    captured = {}
    _fake_oci(monkeypatch, reply, captured)
    client = OCIGenAIClient()
    out = client.extract_entries([{"idx": 0, "text": "hello"}], key)
    assert out == [{"sentence_idx": 0, "concept_id": cid, "status": "correct", "misconception_id": None}]
    d = captured["details"]
    assert d.compartment_id == "ocid1.compartment.test"
    assert d.serving_mode.model_id == "cohere.command-a-03-2025"
    assert d.chat_request.temperature == 0
    assert key.topic in d.chat_request.preamble_override
    assert "us-chicago-1" in captured["endpoint"]


def test_parse_json_text_with_prose():
    assert parse_json_text('Sure: {"entries": []} done') == {"entries": []}
