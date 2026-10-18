"""Session ids. Every lecture, source and exam attempt is stored under one.

  demo, s1, ...            anonymous sessions named by the X-Session-Id header
  user:<id>                a logged in user's free practice
  topic:<id>               a topic's notes, uploaded by the teacher (only sources live here)
  user:<id>:topic:<id>     a student's own Reeta for one topic: what they taught her and her quizzes

The header may never name a reserved one; only a login token reaches them.
"""
import re

RESERVED = ("user:", "topic:")
_STUDENT_TOPIC = re.compile(r"user:(\d+):topic:(\d+)")


def user_session(user_id: int) -> str:
    return f"user:{user_id}"


def topic_notes_session(topic_id: int) -> str:
    return f"topic:{topic_id}"


def student_topic_session(user_id: int, topic_id: int) -> str:
    return f"user:{user_id}:topic:{topic_id}"


def topic_of(session_id: str) -> int | None:
    """The topic a student's session works on, or None for free practice and anonymous sessions."""
    m = _STUDENT_TOPIC.fullmatch(session_id)
    return int(m.group(2)) if m else None


def notes_session_for(session_id: str) -> str:
    """Where the exam's notes come from: the teacher's topic notes for a topic session, else the session itself."""
    topic_id = topic_of(session_id)
    return topic_notes_session(topic_id) if topic_id is not None else session_id


def is_reserved(session_id: str) -> bool:
    return session_id.startswith(RESERVED)
