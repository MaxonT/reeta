import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.accounts import Accounts, check_password, hash_password
from app.classwork import Classwork
from app.llm.mock import MockLLMClient
from app.repo.sqlite_repo import SQLiteRepository
from app.service import ReetaService
from app.speech.base import BrowserSpeechClient


@pytest.fixture
def repo():
    return SQLiteRepository(":memory:")


@pytest.fixture
def client(repo, tmp_path):
    app = FastAPI()
    accounts = Accounts(repo, pass_threshold=1.0)
    app.include_router(accounts.router)
    svc = ReetaService(repo, BrowserSpeechClient(), MockLLMClient(), tmp_path)
    app.include_router(Classwork(svc, accounts, max_source_bytes=200_000).router)

    @app.get("/whoami")  # stands in for every main.py route that takes Session
    def whoami(session_id: str = Depends(accounts.session_id)):
        return {"session_id": session_id}

    return TestClient(app)


def signup(client, email, role, name=None, password="password123"):
    r = client.post("/auth/signup", json={"email": email, "name": name or email.split("@")[0],
                                          "password": password, "role": role})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def add_attempt(repo, user_id, results, prompts=None, topic_id=None):
    """results: list of reasons (correct | wrong | not_taught). Free practice, or on a topic. Returns the attempt id."""
    aid, _ = repo.create_attempt(f"user:{user_id}" + (f":topic:{topic_id}" if topic_id else ""))
    repo.add_answers(aid, [{"question_id": f"q{i}", "prompt": (prompts or {}).get(i, f"Question {i}?"),
                            "answer": "secret answer" if r != "not_taught" else None,
                            "is_correct": r == "correct", "reason": r, "feedback": f"feedback {i}",
                            "quote": "a quote from the recording", "lecture_id": None, "line": "Reeta said this"}
                           for i, r in enumerate(results, 1)])
    repo.set_attempt_score(aid, results.count("correct"))
    return aid


def test_password_hash_round_trip_and_salt():
    h = hash_password("hunter2hunter2")
    assert h.startswith("scrypt$") and "hunter2" not in h
    assert check_password("hunter2hunter2", h)
    assert not check_password("wrong password", h)
    assert hash_password("hunter2hunter2") != h  # salted
    assert not check_password("x", "garbage")


def test_signup_login_me_logout(client):
    out = signup(client, "Ada@Example.com ", "student", name="Ada")
    assert out["user"] == {"id": out["user"]["id"], "email": "ada@example.com", "name": "Ada", "role": "student"}
    token = out["token"]
    me = client.get("/auth/me", headers=auth(token)).json()
    assert me["user"]["email"] == "ada@example.com" and "password_hash" not in me["user"]
    assert me["classes"] == []

    assert client.post("/auth/login", json={"email": "ada@example.com", "password": "nope-nope"}).status_code == 401
    assert client.post("/auth/login", json={"email": "who@example.com", "password": "password123"}).status_code == 401
    token2 = client.post("/auth/login", json={"email": "ADA@example.com", "password": "password123"}).json()["token"]

    client.post("/auth/logout", headers=auth(token))
    assert client.get("/auth/me", headers=auth(token)).status_code == 401
    assert client.get("/auth/me", headers=auth(token2)).status_code == 200


def test_signup_rejects_bad_input_and_duplicate_email(client):
    base = {"email": "a@b.co", "name": "A", "password": "password123", "role": "student"}
    for bad in ({"email": "nope"}, {"name": "  "}, {"password": "short"}, {"role": "admin"}):
        assert client.post("/auth/signup", json=base | bad).status_code == 400, bad
    assert client.post("/auth/signup", json=base).status_code == 200
    assert client.post("/auth/signup", json=base | {"email": "A@B.co"}).status_code == 409


def test_session_is_the_account_and_header_cannot_claim_one(client):
    token = signup(client, "s@x.co", "student")["token"]
    user_id = client.get("/auth/me", headers=auth(token)).json()["user"]["id"]
    assert client.get("/whoami", headers=auth(token)).json() == {"session_id": f"user:{user_id}"}
    # a token wins over the header
    assert client.get("/whoami", headers=auth(token) | {"X-Session-Id": "demo"}).json()["session_id"] == f"user:{user_id}"
    # anonymous still works, as before accounts
    assert client.get("/whoami").json() == {"session_id": "demo"}
    assert client.get("/whoami", headers={"X-Session-Id": "s1"}).json() == {"session_id": "s1"}
    # but cannot read someone's account by naming its session
    assert client.get("/whoami", headers={"X-Session-Id": f"user:{user_id}"}).status_code == 401
    assert client.get("/whoami", headers=auth("made-up")).status_code == 401


def test_class_create_join_and_roles(client):
    t = signup(client, "t@x.co", "teacher", name="Ms T")["token"]
    s = signup(client, "s@x.co", "student")["token"]
    assert client.post("/classes", json={"name": "CS 101"}, headers=auth(s)).status_code == 403
    cls = client.post("/classes", json={"name": "CS 101"}, headers=auth(t)).json()
    assert len(cls["join_code"]) == 6 and cls["student_count"] == 0

    assert client.post("/classes/join", json={"join_code": "NOPE00"}, headers=auth(s)).status_code == 404
    assert client.post("/classes/join", json={"join_code": cls["join_code"]}, headers=auth(t)).status_code == 403
    joined = client.post("/classes/join", json={"join_code": f" {cls['join_code'].lower()} "}, headers=auth(s))
    assert joined.json()["id"] == cls["id"]
    assert client.post("/classes/join", json={"join_code": cls["join_code"]}, headers=auth(s)).status_code == 200

    teacher_me = client.get("/auth/me", headers=auth(t)).json()
    assert [(c["name"], c["student_count"]) for c in teacher_me["classes"]] == [("CS 101", 1)]
    student_me = client.get("/auth/me", headers=auth(s)).json()
    assert [(c["name"], c["teacher_name"]) for c in student_me["classes"]] == [("CS 101", "Ms T")]


def test_gradebook_shows_grades_only_to_the_class_teacher(client, repo):
    t = signup(client, "t@x.co", "teacher")["token"]
    other_t = signup(client, "t2@x.co", "teacher")["token"]
    ada = signup(client, "ada@x.co", "student", name="Ada")
    bo = signup(client, "bo@x.co", "student", name="Bo")
    outsider = signup(client, "out@x.co", "student", name="Out")
    cls = client.post("/classes", json={"name": "CS"}, headers=auth(t)).json()
    for st in (ada, bo):
        client.post("/classes/join", json={"join_code": cls["join_code"]}, headers=auth(st["token"]))
    topic = client.post(f"/classes/{cls['id']}/topics", json={"title": "Recursion"}, headers=auth(t)).json()

    add_attempt(repo, ada["user"]["id"], ["correct", "wrong", "not_taught"], topic_id=topic["id"])
    add_attempt(repo, ada["user"]["id"], ["correct", "correct", "correct"], topic_id=topic["id"])
    repo.create_attempt(f"user:{ada['user']['id']}:topic:{topic['id']}")  # failed to start: not a grade
    add_attempt(repo, ada["user"]["id"], ["wrong"])  # free practice: shown apart from the topics
    add_attempt(repo, outsider["user"]["id"], ["correct"])

    book = client.get(f"/classes/{cls['id']}/gradebook", headers=auth(t)).json()
    rows = {r["student"]["name"]: r["summary"] for r in book["students"]}
    assert list(rows) == ["Ada", "Bo"]
    assert rows["Ada"]["quizzes"] == 2 and rows["Ada"]["passes"] == 1
    assert rows["Ada"]["last"]["score"] == 3 and rows["Ada"]["last"]["percent"] == 100
    assert (rows["Ada"]["best_percent"], rows["Ada"]["average_percent"]) == (100, 67)
    assert (rows["Ada"]["wrong"], rows["Ada"]["not_taught"]) == (1, 1)
    assert rows["Ada"]["streak"] == 1
    assert rows["Bo"]["quizzes"] == 0 and rows["Bo"]["last"] is None
    ada_row = next(r for r in book["students"] if r["student"]["name"] == "Ada")
    assert ada_row["practice"]["quizzes"] == 1 and ada_row["practice"]["last"]["score"] == 0
    assert ada_row["topics"][str(topic["id"])]["status"] == "passed"

    detail = client.get(f"/classes/{cls['id']}/students/{ada['user']['id']}", headers=auth(t)).json()
    assert [t["topic"]["title"] for t in detail["topics"]] == ["Recursion"]
    assert len(detail["practice"]["attempts"]) == 1
    first = detail["topics"][0]["attempts"][0]
    assert (first["score"], first["total"], first["passed"]) == (1, 3, False)
    assert first["questions"][1] == {"question_id": "q2", "prompt": "Question 2?", "result": "wrong",
                                     "feedback": "feedback 2"}
    text = str(detail)
    assert "secret answer" not in text and "a quote from the recording" not in text and "Reeta said" not in text

    # not your class, not your student, not a teacher
    assert client.get(f"/classes/{cls['id']}/gradebook", headers=auth(other_t)).status_code == 404
    assert client.get(f"/classes/{cls['id']}/students/{outsider['user']['id']}", headers=auth(t)).status_code == 404
    assert client.get(f"/classes/{cls['id']}/gradebook", headers=auth(ada["token"])).status_code == 403
    assert client.get(f"/classes/{cls['id']}/gradebook").status_code == 401


def test_my_progress_for_a_student(client, repo):
    s = signup(client, "s@x.co", "student")
    assert client.get("/me/progress", headers=auth(s["token"])).json()["quizzes"] == 0
    add_attempt(repo, s["user"]["id"], ["correct", "wrong"])
    progress = client.get("/me/progress", headers=auth(s["token"])).json()
    assert progress["last"]["score"] == 1 and progress["last"]["passed"] is False



def test_malformed_or_missing_authorization(client):
    for header in ("Basic abc", "Bearer ", "Bearer", "token-without-scheme"):
        assert client.get("/auth/me", headers={"Authorization": header}).status_code == 401, header
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/logout").json() == {"ok": True}  # logging out twice is harmless


def test_role_checks_on_every_role_route(client):
    t = signup(client, "t@x.co", "teacher")["token"]
    s = signup(client, "s@x.co", "student")["token"]
    assert client.get("/me/progress", headers=auth(t)).status_code == 403
    assert client.post("/classes/join", json={"join_code": "AAAAAA"}, headers=auth(t)).status_code == 403
    assert client.post("/classes", json={"name": "X"}, headers=auth(s)).status_code == 403
    assert client.get("/classes/1/students/1", headers=auth(s)).status_code == 403
    for path in ("/me/progress", "/classes/1/gradebook", "/classes/1/students/1"):
        assert client.get(path).status_code == 401, path


def test_class_name_validation_and_unknown_class(client):
    t = signup(client, "t@x.co", "teacher")["token"]
    assert client.post("/classes", json={"name": "   "}, headers=auth(t)).status_code == 400
    assert client.post("/classes", json={"name": "x" * 201}, headers=auth(t)).status_code == 400
    assert client.get("/classes/999/gradebook", headers=auth(t)).status_code == 404


def test_join_codes_are_unique_and_unambiguous(client):
    t = signup(client, "t@x.co", "teacher")["token"]
    codes = [client.post("/classes", json={"name": f"C{i}"}, headers=auth(t)).json()["join_code"] for i in range(20)]
    assert len(set(codes)) == 20
    assert not set("".join(codes)) & set("01OIL")


def test_a_student_in_two_classes_shows_in_both_gradebooks(client, repo):
    t1 = signup(client, "t1@x.co", "teacher")["token"]
    t2 = signup(client, "t2@x.co", "teacher")["token"]
    s = signup(client, "s@x.co", "student", name="Sam")
    c1 = client.post("/classes", json={"name": "Math"}, headers=auth(t1)).json()
    c2 = client.post("/classes", json={"name": "CS"}, headers=auth(t2)).json()
    for c in (c1, c2):
        client.post("/classes/join", json={"join_code": c["join_code"]}, headers=auth(s["token"]))
    math = client.post(f"/classes/{c1['id']}/topics", json={"title": "Fractions"}, headers=auth(t1)).json()
    add_attempt(repo, s["user"]["id"], ["correct"], topic_id=math["id"])
    for c, t, quizzes in ((c1, t1, 1), (c2, t2, 0)):  # a Math topic grade is not a CS grade
        book = client.get(f"/classes/{c['id']}/gradebook", headers=auth(t)).json()
        assert [(r["student"]["name"], r["summary"]["quizzes"]) for r in book["students"]] == [("Sam", quizzes)]
    me = client.get("/auth/me", headers=auth(s["token"])).json()
    assert [c["name"] for c in me["classes"]] == ["Math", "CS"]
