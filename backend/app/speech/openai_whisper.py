from pathlib import Path

from ..config import settings
from .base import SpeechClient


class OpenAIWhisperClient(SpeechClient):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.openai_api_key or None)

    def transcribe(self, audio_path: Path) -> dict:
        with open(audio_path, "rb") as f:
            resp = self.client.audio.transcriptions.create(
                model=settings.openai_whisper_model,
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["word"],
                language="en",
            )
        words = [
            {"w": w.word.strip(), "start_ms": int(w.start * 1000), "end_ms": int(w.end * 1000)}
            for w in (resp.words or []) if w.word.strip()
        ]
        return {"text": (resp.text or "").strip(), "words": words}
