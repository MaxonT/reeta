"""Storage interface. Business logic (supersede, grading) never touches SQL."""
from abc import ABC, abstractmethod


class Repository(ABC):
    @abstractmethod
    def seed_content(self, concepts: list[dict], questions: list[dict],
                     edges: list[tuple[str, str]] | None = None) -> None: ...
    @abstractmethod
    def list_edges(self) -> list[tuple[str, str]]:
        """Concept edges as (source_id, target_id), in seed order."""

    # Lectures and sentences
    @abstractmethod
    def create_lecture(self, session_id: str, kind: str, text: str) -> int: ...
    @abstractmethod
    def update_lecture(self, lecture_id: int, **fields) -> None:
        """fields among audio_path, text"""
    @abstractmethod
    def get_lecture(self, lecture_id: int) -> dict | None: ...
    @abstractmethod
    def list_lectures(self, session_id: str) -> list[dict]:
        """Lectures with their sentences, oldest first."""
    @abstractmethod
    def add_sentences(self, lecture_id: int, sentences: list[dict]) -> list[dict]: ...

    # Notebook entries (never deleted; replaced via superseded_by)
    @abstractmethod
    def add_entries(self, session_id: str, entries: list[dict]) -> list[dict]: ...
    @abstractmethod
    def list_entries(self, session_id: str, confirmed_only: bool = False) -> list[dict]:
        """Entries with joined `sentence`, ordered by id."""
    @abstractmethod
    def update_entry(self, entry_id: int, **fields) -> None:
        """fields among concept_id, status, misconception_id, confirmed, superseded_by"""

    # Exam
    @abstractmethod
    def list_questions(self) -> list[dict]: ...
    @abstractmethod
    def create_attempt(self, session_id: str, score: int) -> tuple[int, int]:
        """-> (attempt_id, attempt_no)"""
    @abstractmethod
    def add_answers(self, attempt_id: int, answers: list[dict]) -> None: ...
    @abstractmethod
    def list_attempts(self, session_id: str) -> list[dict]:
        """Attempts with their `answers`, oldest first."""

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
