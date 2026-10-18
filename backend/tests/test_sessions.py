from app.sessions import (is_reserved, notes_session_for, student_topic_session, topic_notes_session, topic_of,
                          user_session)


def test_session_names():
    assert user_session(4) == "user:4"
    assert topic_notes_session(7) == "topic:7"
    assert student_topic_session(4, 7) == "user:4:topic:7"


def test_topic_of_and_notes_session():
    assert topic_of("user:4:topic:7") == 7
    for s in ("user:4", "demo", "topic:7", "user:4:topic:x", "user:4:topic:7:extra"):
        assert topic_of(s) is None, s
    assert notes_session_for("user:4:topic:7") == "topic:7"  # quizzes on the teacher's notes
    assert notes_session_for("user:4") == "user:4" and notes_session_for("demo") == "demo"


def test_reserved_sessions():
    assert is_reserved("user:4") and is_reserved("topic:7") and is_reserved("user:4:topic:7")
    assert not is_reserved("demo") and not is_reserved("s1") and not is_reserved("users")
