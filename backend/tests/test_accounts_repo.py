"""Repository account and class methods, straight against SQLite (Oracle has the same interface, see
test_oracle_repo.py)."""
import pytest

from app.repo.sqlite_repo import SQLiteRepository


@pytest.fixture
def repo():
    return SQLiteRepository(":memory:")


def users(repo):
    t = repo.create_user("t@x.co", "Teacher", "teacher", "hash-t")
    a = repo.create_user("a@x.co", "Zed", "student", "hash-a")
    b = repo.create_user("b@x.co", "Amy", "student", "hash-b")
    return t, a, b


def test_create_user_and_duplicate_email(repo):
    uid = repo.create_user("a@x.co", "A", "student", "h")
    assert isinstance(uid, int)
    assert repo.create_user("a@x.co", "Other", "teacher", "h2") is None


def test_password_hash_only_comes_back_for_login(repo):
    uid = repo.create_user("a@x.co", "A", "student", "the-hash")
    user = repo.get_user(uid)
    assert set(user) == {"id", "email", "name", "role", "created_at"}
    assert repo.get_user_by_email("a@x.co")["password_hash"] == "the-hash"
    assert repo.get_user(999) is None and repo.get_user_by_email("nobody@x.co") is None


def test_tokens_expire_and_can_be_deleted(repo):
    uid = repo.create_user("a@x.co", "A", "student", "h")
    repo.create_token("live", uid, expires_at=2000)
    repo.create_token("old", uid, expires_at=1000)
    assert repo.user_for_token("live", now=1500)["id"] == uid
    assert "password_hash" not in repo.user_for_token("live", now=1500)
    assert repo.user_for_token("old", now=1500) is None   # expired
    assert repo.user_for_token("live", now=2000) is None  # expiry is exclusive
    assert repo.user_for_token("unknown", now=0) is None
    repo.delete_token("live")
    assert repo.user_for_token("live", now=1500) is None
    repo.delete_token("never-existed")  # no error


def test_classes_codes_and_lookup(repo):
    t, _, _ = users(repo)
    cid = repo.create_class(t, "CS 101", "ABC234")
    assert repo.create_class(t, "CS 102", "ABC234") is None  # code taken
    assert repo.get_class(cid)["name"] == "CS 101"
    assert repo.class_by_code("ABC234")["id"] == cid
    assert repo.class_by_code("ZZZZZZ") is None and repo.get_class(999) is None


def test_membership_counts_and_ordering(repo):
    t, zed, amy = users(repo)
    other_t = repo.create_user("t2@x.co", "Other", "teacher", "h")
    c1 = repo.create_class(t, "First", "AAAAAA")
    c2 = repo.create_class(t, "Second", "BBBBBB")
    c3 = repo.create_class(other_t, "Theirs", "CCCCCC")

    assert repo.add_member(c1, zed) is True
    assert repo.add_member(c1, zed) is False  # already in
    repo.add_member(c1, amy)
    repo.add_member(c3, zed)

    assert [(c["name"], c["student_count"]) for c in repo.list_teacher_classes(t)] == [("First", 2), ("Second", 0)]
    assert [c["name"] for c in repo.list_teacher_classes(other_t)] == ["Theirs"]
    assert [(c["name"], c["teacher_name"]) for c in repo.list_student_classes(zed)] == [("First", "Teacher"),
                                                                                        ("Theirs", "Other")]
    assert repo.list_student_classes(amy)[0]["name"] == "First"

    members = repo.list_members(c1)
    assert [m["name"] for m in members] == ["Amy", "Zed"]  # by name
    assert all("password_hash" not in m and m["joined_at"] for m in members)
    assert repo.list_members(c2) == []

    assert repo.is_member(c1, zed) and not repo.is_member(c2, zed) and not repo.is_member(c1, t)


def test_reset_session_leaves_accounts_alone(repo):
    t, zed, _ = users(repo)
    cid = repo.create_class(t, "C", "AAAAAA")
    repo.add_member(cid, zed)
    repo.reset_session(f"user:{zed}")
    assert repo.get_user(zed) and repo.is_member(cid, zed)


def test_topics(repo):
    t, _, _ = users(repo)
    c1, c2 = repo.create_class(t, "A", "AAAAAA"), repo.create_class(t, "B", "BBBBBB")
    first = repo.create_topic(c1, "Recursion", "Base cases please", 3)
    repo.create_topic(c1, "Loops", "", 5)
    repo.create_topic(c2, "Other", "", 2)
    assert [x["title"] for x in repo.list_topics(c1)] == ["Recursion", "Loops"]
    got = repo.get_topic(first)
    assert (got["class_id"], got["instructions"], got["questions_per_quiz"]) == (c1, "Base cases please", 3)
    repo.update_topic(first, title="Recursion 2", questions_per_quiz=4)
    got = repo.get_topic(first)
    assert (got["title"], got["questions_per_quiz"], got["instructions"]) == ("Recursion 2", 4, "Base cases please")
    with pytest.raises(ValueError):
        repo.update_topic(first, class_id=c2)  # a topic never moves class
    assert repo.get_topic(999) is None and repo.list_topics(999) == []
