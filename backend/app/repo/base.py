"""Storage interface. Business logic (grading, Reeta's answers) never touches SQL."""
from abc import ABC, abstractmethod


class Repository(ABC):
    @abstractmethod
    def seed_content(self, concepts: list[dict], questions: list[dict],
                     edges: list[tuple[str, str]] | None = None) -> None: ...
    @abstractmethod
    def list_edges(self) -> list[tuple[str, str]]:
        """Concept edges as (source_id, target_id), in seed order."""

    # Lectures: Reeta's memory is their transcripts
    @abstractmethod
    def create_lecture(self, session_id: str, kind: str, text: str) -> int: ...
    @abstractmethod
    def update_lecture(self, lecture_id: int, **fields) -> None:
        """fields among audio_path, text, words (list of {w, start_ms, end_ms})"""
    @abstractmethod
    def get_lecture(self, lecture_id: int) -> dict | None:
        """`words` comes back as a parsed list."""
    @abstractmethod
    def list_lectures(self, session_id: str) -> list[dict]:
        """Oldest first."""

    # Source material the exam questions are written from
    @abstractmethod
    def add_source(self, session_id: str, filename: str, text: str) -> int: ...
    @abstractmethod
    def list_sources(self, session_id: str) -> list[dict]:
        """Oldest first, with full `text`."""
    @abstractmethod
    def delete_source(self, session_id: str, source_id: int) -> bool:
        """False if that source does not exist in this session."""

    # Exam
    @abstractmethod
    def list_questions(self) -> list[dict]: ...
    @abstractmethod
    def create_attempt(self, session_id: str) -> tuple[int, int]:
        """-> (attempt_id, attempt_no)"""
    @abstractmethod
    def set_attempt_score(self, attempt_id: int, score: int) -> None: ...
    @abstractmethod
    def add_answers(self, attempt_id: int, answers: list[dict]) -> None:
        """answer keys: question_id, answer, is_correct, reason; optional: prompt, reference_answer,
        feedback, lecture_id, quote, quote_start_ms, quote_end_ms, line"""
    @abstractmethod
    def list_attempts(self, session_id: str) -> list[dict]:
        """Attempts with their `answers`, oldest first."""

    # Daily loop (short quiz rounds that drive the streak)
    @abstractmethod
    def add_round(self, session_id: str, created_at: str, lecture_id: int | None, score: int, total: int,
                  passed: bool, concept_ids: list[str]) -> int:
        """-> round id. created_at is an ISO 8601 timestamp."""
    @abstractmethod
    def list_rounds(self, session_id: str) -> list[dict]:
        """Rounds oldest first: {id, session_id, created_at, lecture_id, score, total, passed (bool), concept_ids}."""

    @abstractmethod
    def reset_session(self, session_id: str) -> None: ...


def get_repository(provider: str) -> Repository:
    from ..config import settings
    if provider == "sqlite":
        from .sqlite_repo import SQLiteRepository
        return SQLiteRepository(settings.sqlite_path)
    if provider == "oracle":
        from .oracle_repo import OracleRepository
        return OracleRepository()
    raise ValueError(f"unknown DB_PROVIDER {provider!r}")
