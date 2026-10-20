from abc import ABC, abstractmethod
from pathlib import Path


class SpeechClient(ABC):
    """Audio file -> {"text": str, "words": [{w, start_ms, end_ms}]}."""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> dict: ...


class BrowserSpeechClient(SpeechClient):
    """Server does no transcription; the frontend's Web Speech API transcript is used."""

    def transcribe(self, audio_path: Path) -> dict:
        raise NotImplementedError("browser provider: transcript must come from the frontend")


def get_speech_client(provider: str) -> SpeechClient:
    if provider == "openai":
        from .openai_whisper import OpenAIWhisperClient
        return OpenAIWhisperClient()
    if provider == "browser":
        return BrowserSpeechClient()
    raise ValueError(f"unknown SPEECH_PROVIDER {provider!r}")
