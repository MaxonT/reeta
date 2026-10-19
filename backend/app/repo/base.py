"""Storage interface. Business logic (grading, Reeta's answers) never touches SQL."""
from abc import ABC, abstractmethod


class Repository(ABC):
    @abstractmethod
    def seed_content(self, questions: list[dict]) -> None:
        """Upsert Exam questions: id, type, prompt, options, correct_answer."""

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

    @abstractmethod
    def reset_session(self, session_id: str) -> None: ...

    # Accounts. User dicts never carry password_hash except from get_user_by_email (login needs it).
    @abstractmethod
    def create_user(self, email: str, name: str, role: str, password_hash: str) -> int | None:
        """None if that email is taken."""
    @abstractmethod
    def get_user(self, user_id: int) -> dict | None: ...
    @abstractmethod
    def get_user_by_email(self, email: str) -> dict | None:
        """Includes password_hash."""
    @abstractmethod
    def create_token(self, token_hash: str, user_id: int, expires_at: int) -> None: ...
    @abstractmethod
    def user_for_token(self, token_hash: str, now: int) -> dict | None:
        """The token's user, or None if it is unknown or expired."""
    @abstractmethod
    def delete_token(self, token_hash: str) -> None: ...

    # Classes
    @abstractmethod
    def create_class(self, teacher_id: int, name: str, join_code: str) -> int | None:
        """None if that join code is taken."""
    @abstractmethod
    def get_class(self, class_id: int) -> dict | None: ...
    @abstractmethod
    def class_by_code(self, join_code: str) -> dict | None: ...
    @abstractmethod
    def list_teacher_classes(self, teacher_id: int) -> list[dict]:
        """Oldest first, each with student_count."""
    @abstractmethod
    def list_student_classes(self, student_id: int) -> list[dict]:
        """Oldest joined first, each with teacher_name."""
    @abstractmethod
    def add_member(self, class_id: int, student_id: int) -> bool:
        """False if already a member."""
    @abstractmethod
    def list_members(self, class_id: int) -> list[dict]:
        """Users with joined_at, ordered by name."""
    @abstractmethod
    def is_member(self, class_id: int, student_id: int) -> bool: ...

    # Topics a teacher sets for a class. Their notes are sources under sessions.topic_notes_session().
    @abstractmethod
    def create_topic(self, class_id: int, title: str, instructions: str, questions_per_quiz: int) -> int: ...
    @abstractmethod
    def get_topic(self, topic_id: int) -> dict | None: ...
    @abstractmethod
    def list_topics(self, class_id: int) -> list[dict]:
        """Oldest first."""
    @abstractmethod
    def update_topic(self, topic_id: int, **fields) -> None:
        """fields among title, instructions, questions_per_quiz"""


def get_repository(provider: str) -> Repository:
    from ..config import settings
    if provider == "sqlite":
        from .sqlite_repo import SQLiteRepository
        return SQLiteRepository(settings.sqlite_path)
    if provider == "postgres":
        from .postgres_repo import PostgresRepository
        return PostgresRepository(settings.postgres_url)
    raise ValueError(f"unknown DB_PROVIDER {provider!r}")
