"""Settings from environment variables. All keys stay on the backend."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "backend" / ".env")


def _path(value: str) -> Path:
    if value == ":memory:":
        return Path(value)
    p = Path(value).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass(frozen=True)
class Settings:
    speech_provider: str = os.getenv("SPEECH_PROVIDER", "openai").lower()
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock").lower()
    db_provider: str = os.getenv("DB_PROVIDER", "sqlite").lower()
    question_source: str = os.getenv("QUESTION_SOURCE", "llm").lower()  # llm | fixed
    question_file: str = os.getenv("QUESTION_FILE", "photosynthesis_questions.json")  # in CONTENT_DIR, for fixed
    question_shuffle: bool = os.getenv("QUESTION_SHUFFLE", "false").lower() in ("1", "true", "yes")  # fixed: random pick
    sqlite_path: Path = _path(os.getenv("SQLITE_PATH", "backend/data/reeta.db"))
    postgres_url: str = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL", "")
    audio_dir: Path = _path(os.getenv("AUDIO_DIR", "backend/data/audio"))
    content_dir: Path = _path(os.getenv("CONTENT_DIR", "content"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_whisper_model: str = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
    oci_config_file: str = os.getenv("OCI_CONFIG_FILE", "~/.oci/config")
    oci_profile: str = os.getenv("OCI_PROFILE", "DEFAULT")
    oci_region: str = os.getenv("OCI_REGION", "us-chicago-1")
    oci_compartment_id: str = os.getenv("OCI_COMPARTMENT_ID", "")
    oci_genai_model_id: str = os.getenv("OCI_GENAI_MODEL_ID", "")
    oracle_user: str = os.getenv("ORACLE_USER", "ADMIN")
    oracle_password: str = os.getenv("ORACLE_PASSWORD", "")
    oracle_dsn: str = os.getenv("ORACLE_DSN", "")
    oracle_wallet_dir: str = os.getenv("ORACLE_WALLET_DIR", "backend/wallet")
    oracle_wallet_password: str = os.getenv("ORACLE_WALLET_PASSWORD", "")
    max_source_chars: int = int(os.getenv("MAX_SOURCE_CHARS", "50000"))  # per uploaded source
    max_notes_chars: int = int(os.getenv("MAX_NOTES_CHARS", "60000"))    # all sources together, in the prompt
    pass_threshold: float = float(os.getenv("PASS_THRESHOLD", "1.0"))


settings = Settings()
