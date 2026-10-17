"""OCI Generative AI client (us-chicago-1). STUB, not wired yet.

TODO(oci):
  1. pip install oci; config from OCI_CONFIG_FILE / OCI_PROFILE
  2. client = oci.generative_ai_inference.GenerativeAiInferenceClient(
         config, service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com")
  3. client.chat(ChatDetails(compartment_id=OCI_COMPARTMENT_ID,
         serving_mode=OnDemandServingMode(model_id=OCI_GENAI_MODEL_ID),
         chat_request=GenericChatRequest(messages=[...], temperature=0)))
  4. Reuse EXTRACT_SYSTEM / PHRASE_SYSTEM from openai_client.py, parse JSON,
     and ALWAYS pass the result through validate_entries().
Until then get_llm_client("oci") wraps this in FallbackLLMClient, so the Mock answers.
"""
from ..content import AnswerKey
from .base import LLMClient


class OCIGenAIClient(LLMClient):
    def extract_entries(self, sentences: list[dict], key: AnswerKey) -> list[dict]:
        raise NotImplementedError("OCIGenAIClient is a stub. See TODO in llm/oci_genai.py")

    def phrase(self, result: dict, question: dict, key: AnswerKey) -> str:
        raise NotImplementedError("OCIGenAIClient is a stub. See TODO in llm/oci_genai.py")
