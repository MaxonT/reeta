from pathlib import Path

from ..config import settings
from ..sentences import segments_to_sentences
from .base import SpeechClient


class OpenAIWhisperClient(SpeechClient):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.openai_api_key or None)

    def transcribe(self, audio_path: Path) -> list[dict]:
        with open(audio_path, "rb") as f:
            resp = self.client.audio.transcriptions.create(
                model=settings.openai_whisper_model,
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language="en",
            )
        segments = [
            {"text": s.text, "start_ms": int(s.start * 1000), "end_ms": int(s.end * 1000)}
            for s in (resp.segments or [])
        ]
        if not segments and resp.text:
            segments = [{"text": resp.text, "start_ms": 0, "end_ms": int((resp.duration or 0) * 1000)}]
        return segments_to_sentences(segments)
