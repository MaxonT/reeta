"""Settings from environment variables. All keys stay on the backend."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "backend" / ".env")


def _path(value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass(frozen=True)
class Settings:
    speech_provider: str = os.getenv("SPEECH_PROVIDER", "openai").lower()
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock").lower()
    db_provider: str = os.getenv("DB_PROVIDER", "sqlite").lower()
    sqlite_path: Path = _path(os.getenv("SQLITE_PATH", "backend/data/reeta.db"))
    audio_dir: Path = _path(os.getenv("AUDIO_DIR", "backend/data/audio"))
    content_dir: Path = _path(os.getenv("CONTENT_DIR", "content"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_whisper_model: str = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
    pass_threshold: float = float(os.getenv("PASS_THRESHOLD", "1.0"))


settings = Settings()
