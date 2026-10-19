"""Accounts through the real app in main.py: every existing route follows the logged in account's session."""
import importlib
import json
import sys

import pytest
from fastapi.testclient import TestClient

from app.config import settings

OFFLINE = {"speech_provider": "browser", "llm_provider": "mock", "db_provider": "sqlite",
           "sqlite_path": ":memory:", "pass_threshold": 1.0}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # main.py builds its service from `settings` at import, so point settings offline first, then (re)import.
    patch = OFFLINE | {"audio_dir": tmp_path_factory.mktemp("audio")}
    saved = {k: getattr(settings, k) for k in patch}
    for k, v in patch.items():
        object.__setattr__(settings, k, v)  # Settings is frozen
    try:
        main = importlib.reload(sys.modules["app.main"]) if "app.main" in sys.modules else importlib.import_module("app.main")
        yield TestClient(main.app)
    finally:
        for k, v in saved.items():
            object.__setattr__(settings, k, v)


_n = 0


def signup(client, role, name="Someone"):
    global _n
    _n += 1
    r = client.post("/auth/signup", json={"email": f"{role}{_n}@x.co", "name": name, "password": "password123",
                                          "role": role})
    assert r.status_code == 200, r.text
    out = r.json()
    return {"Authorization": f"Bearer {out['token']}"}, out["user"]


def teach(client, headers, text, audio: bytes | None = None):
    files = {"audio": ("lecture.webm", audio, "audio/webm")} if audio else None
    r = client.post("/lectures/audio", data={"text": text, "kind": "lecture"}, files=files, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["lecture"]


def run_exam(client, headers, n=2):
    events = []
    with client.stream("POST", f"/exam/run?questions={n}", headers=headers) as r:
        assert r.status_code == 200
        block = ""
        for chunk in r.iter_text():
            block += chunk
            while "\n\n" in block:
                ev, block = block.split("\n\n", 1)
                lines = dict(line.split(": ", 1) for line in ev.splitlines() if ": " in line)
                events.append((lines.get("event"), json.loads(lines.get("data", "null"))))
    names = [e for e, _ in events]
    assert "error" not in names, events
    return dict(events)["done"]


def test_health_still_works(client):
    assert client.get("/health").json()["ok"] is True


def test_anonymous_sessions_work_as_before(client):
    client.post("/session/reset", headers={"X-Session-Id": "anon-a"})
    r = client.post("/sources", data={"text": "Notes about recursion."}, headers={"X-Session-Id": "anon-a"})
    assert r.status_code == 200
    assert len(client.get("/sources", headers={"X-Session-Id": "anon-a"}).json()["sources"]) == 1
    assert client.get("/sources", headers={"X-Session-Id": "anon-b"}).json()["sources"] == []
    assert client.post("/session/reset").status_code == 200  # demo can still reset


def test_header_cannot_reach_an_account_session(client):
    _, user = signup(client, "student")
    spoof = {"X-Session-Id": f"user:{user['id']}"}
    for method, path in (("get", "/lectures"), ("get", "/sources"), ("post", "/session/reset"),
                         ("post", "/exam/run")):
        assert getattr(client, method)(path, headers=spoof).status_code == 401, path


def test_students_data_is_kept_apart(client):
    ada, _ = signup(client, "student", "Ada")
    bo, _ = signup(client, "student", "Bo")
    teach(client, ada, "A recursive function calls itself.")
    client.post("/sources", data={"text": "Ada's notes"}, headers=ada)

    assert len(client.get("/lectures", headers=ada).json()["lectures"]) == 1
    assert client.get("/lectures", headers=bo).json()["lectures"] == []
    assert client.get("/sources", headers=bo).json()["sources"] == []
    ada_source = client.get("/sources", headers=ada).json()["sources"][0]["id"]
    assert client.delete(f"/sources/{ada_source}", headers=bo).status_code == 404  # cannot delete Ada's
    assert client.delete(f"/sources/{ada_source}", headers=ada).status_code == 200


def test_lecture_audio_only_for_its_owner(client):
    owner, _ = signup(client, "student")
    other, _ = signup(client, "student")
    teacher, _ = signup(client, "teacher")
    lec = teach(client, owner, "Typed backup.", audio=b"fake webm bytes")
    url = f"/lectures/{lec['id']}/audio"
    r = client.get(url, headers=owner)
    assert r.status_code == 200 and r.content == b"fake webm bytes"
    for headers in (other, teacher, {}, {"X-Session-Id": "demo"}):
        assert client.get(url, headers=headers).status_code == 404


def test_accounts_cannot_reset_their_gradebook(client):
    s, _ = signup(client, "student")
    assert client.post("/session/reset", headers=s).status_code == 403


NOTES = ("Photosynthesis turns light energy into chemical energy in the chloroplast. "
         "The light reactions split water and release oxygen as a by-product. "
         "The Calvin cycle uses carbon dioxide to build glucose for the plant.")
LESSON = "Photosynthesis turns light energy into chemical energy in the chloroplast."


def class_with_topic(client, questions=2):
    """A teacher, a class with one topic and its notes, and a student in the class."""
    teacher, _ = signup(client, "teacher", "Ms T")
    cls = client.post("/classes", json={"name": "Bio"}, headers=teacher).json()
    topic = client.post(f"/classes/{cls['id']}/topics", headers=teacher, json={
        "title": "Photosynthesis", "instructions": "Explain where glucose comes from.",
        "questions_per_quiz": questions}).json()
    assert client.post(f"/topics/{topic['id']}/notes", data={"text": NOTES}, headers=teacher).status_code == 200
    student, student_user = signup(client, "student", "Ada")
    client.post("/classes/join", json={"join_code": cls["join_code"]}, headers=student)
    return teacher, cls, topic, student, student_user


def on(headers, topic):
    return headers | {"X-Topic-Id": str(topic["id"])}


def test_teacher_creates_and_edits_topics(client):
    teacher, cls, topic, student, _ = class_with_topic(client)
    assert topic["title"] == "Photosynthesis" and topic["notes_count"] == 0 and topic["questions_per_quiz"] == 2
    url = f"/classes/{cls['id']}/topics"
    assert client.get(url, headers=teacher).json()["topics"][0]["notes_count"] == 1  # after the notes upload
    for bad in ({"title": " "}, {"title": "x" * 201}, {"title": "T", "questions_per_quiz": 0},
                {"title": "T", "questions_per_quiz": 11}, {"title": "T", "instructions": "x" * 2001}):
        assert client.post(url, json=bad, headers=teacher).status_code == 400, bad
    assert client.post(url, json={"title": "T"}, headers=student).status_code == 403

    edited = client.patch(f"/topics/{topic['id']}", json={"instructions": "Now also the Calvin cycle."},
                          headers=teacher).json()
    assert edited["instructions"] == "Now also the Calvin cycle." and edited["title"] == "Photosynthesis"
    assert client.patch(f"/topics/{topic['id']}", json={"questions_per_quiz": 50}, headers=teacher).status_code == 400
    assert [t["title"] for t in client.get(url, headers=teacher).json()["topics"]] == ["Photosynthesis"]

    other, _ = signup(client, "teacher")
    assert client.get(url, headers=other).status_code == 404
    assert client.patch(f"/topics/{topic['id']}", json={"title": "Mine"}, headers=other).status_code == 404
    assert client.post(f"/topics/{topic['id']}/notes", data={"text": "x"}, headers=other).status_code == 404


def test_teacher_notes_and_what_students_see(client):
    teacher, cls, topic, student, _ = class_with_topic(client)
    seen = client.get(f"/topics/{topic['id']}", headers=student).json()
    assert seen["class_name"] == "Bio" and seen["instructions"] == "Explain where glucose comes from."
    assert [n["filename"] for n in seen["notes"]] == ["pasted notes"]
    assert seen["progress"]["status"] == "not_started"
    assert "text" not in seen["notes"][0]  # the list, not the notes themselves

    mine = client.get("/me/topics", headers=student).json()["topics"]
    assert [(t["title"], t["class_name"], t["progress"]["status"]) for t in mine] == [("Photosynthesis", "Bio",
                                                                                      "not_started")]
    outsider, _ = signup(client, "student")
    assert client.get(f"/topics/{topic['id']}", headers=outsider).status_code == 404
    assert client.get("/me/topics", headers=outsider).json() == {"topics": []}

    note_id = seen["notes"][0]["id"]
    assert client.delete(f"/topics/{topic['id']}/notes/{note_id}", headers=student).status_code == 403
    assert client.delete(f"/topics/{topic['id']}/notes/{note_id}", headers=teacher).status_code == 200
    assert client.delete(f"/topics/{topic['id']}/notes/{note_id}", headers=teacher).status_code == 404


def test_topic_header_rules(client):
    teacher, cls, topic, student, user = class_with_topic(client)
    outsider, _ = signup(client, "student")
    assert client.get("/lectures", headers={"X-Topic-Id": str(topic["id"])}).status_code == 401
    assert client.get("/lectures", headers=on(teacher, topic)).status_code == 403
    assert client.get("/lectures", headers=on(outsider, topic)).status_code == 404
    assert client.get("/lectures", headers=student | {"X-Topic-Id": "99999"}).status_code == 404
    for spoof in (f"topic:{topic['id']}", f"user:{user['id']}:topic:{topic['id']}"):
        assert client.get("/sources", headers={"X-Session-Id": spoof}).status_code == 401, spoof


def test_a_topic_quiz_is_written_from_the_teacher_notes(client):
    teacher, cls, topic, student, user = class_with_topic(client, questions=2)
    s = on(student, topic)
    assert [x["filename"] for x in client.get("/sources", headers=s).json()["sources"]] == ["pasted notes"]
    assert client.post("/sources", data={"text": "my own notes"}, headers=s).status_code == 403
    note_id = client.get("/sources", headers=s).json()["sources"][0]["id"]
    assert client.delete(f"/sources/{note_id}", headers=s).status_code == 403

    teach(client, s, LESSON)
    assert client.get(f"/topics/{topic['id']}", headers=student).json()["progress"]["status"] == "practicing"
    done = run_exam(client, s, n=5)  # the teacher's questions_per_quiz wins over the client's n
    assert done["total"] == 2
    detail = client.get(f"/classes/{cls['id']}/students/{user['id']}", headers=teacher).json()
    prompts = [q["prompt"] for q in detail["topics"][0]["attempts"][0]["questions"]]
    assert prompts and all(p.split(": ", 1)[1].split()[0] in NOTES for p in prompts), prompts


def test_no_quiz_on_a_topic_without_notes(client):
    teacher, cls, topic, student, _ = class_with_topic(client)
    bare = client.post(f"/classes/{cls['id']}/topics", json={"title": "Empty"}, headers=teacher).json()
    r = client.post("/exam/run", headers=on(student, bare))
    assert r.status_code == 409 and "notes" in r.json()["detail"]


def test_each_topic_has_its_own_reeta(client):
    teacher, cls, topic, student, user = class_with_topic(client)
    other = client.post(f"/classes/{cls['id']}/topics", json={"title": "Cells"}, headers=teacher).json()
    client.post(f"/topics/{other['id']}/notes", data={"text": NOTES}, headers=teacher)
    teach(client, on(student, topic), LESSON)

    assert len(client.get("/lectures", headers=on(student, topic)).json()["lectures"]) == 1
    assert client.get("/lectures", headers=on(student, other)).json()["lectures"] == []
    assert client.get("/lectures", headers=student).json()["lectures"] == []  # free practice is separate too
    done = run_exam(client, on(student, other))
    assert done["score"] == 0  # nothing taught on this topic, so Reeta knows nothing


def test_topic_quizzes_land_in_the_teacher_gradebook(client):
    teacher, cls, topic, ada, ada_user = class_with_topic(client, questions=1)
    lazy, lazy_user = signup(client, "student", "Lazy")
    client.post("/classes/join", json={"join_code": cls["join_code"]}, headers=lazy)

    teach(client, on(ada, topic), LESSON)
    done = run_exam(client, on(ada, topic))
    run_exam(client, on(lazy, topic))  # taught nothing
    teach(client, lazy, "Free practice lesson about recursion calling itself.")
    client.post("/sources", data={"text": "Recursion is when a function calls itself to solve smaller problems."},
                headers=lazy)  # free practice has no teacher notes, so the student brings their own
    run_exam(client, lazy)  # free practice: not a topic grade

    book = client.get(f"/classes/{cls['id']}/gradebook", headers=teacher).json()
    assert book["topics"] == [{"id": topic["id"], "title": "Photosynthesis", "questions_per_quiz": 1}]
    rows = {r["student"]["name"]: r for r in book["students"]}
    ada_topic = rows["Ada"]["topics"][str(topic["id"])]
    assert ada_topic["quizzes"] == 1 and ada_topic["last"]["score"] == done["score"]
    assert ada_topic["status"] == ("passed" if done["passed"] else "practicing")
    assert rows["Ada"]["summary"]["quizzes"] == 1
    lazy_row = rows["Lazy"]
    assert lazy_row["topics"][str(topic["id"])]["status"] == "practicing"  # took a quiz, never passed
    assert lazy_row["summary"]["quizzes"] == 1 and lazy_row["summary"]["not_taught"] == 1
    assert lazy_row["practice"]["quizzes"] == 1

    detail = client.get(f"/classes/{cls['id']}/students/{ada_user['id']}", headers=teacher).json()
    assert detail["student"]["name"] == "Ada" and len(detail["topics"][0]["attempts"]) == 1
    q = detail["topics"][0]["attempts"][0]["questions"][0]
    assert set(q) == {"question_id", "prompt", "result", "feedback"}
    text = json.dumps(detail)
    assert LESSON not in text and "chemical energy in the chloroplast." not in text.replace(q["prompt"], "")
    assert client.get(f"/classes/{cls['id']}/students/{lazy_user['id']}", headers=ada).status_code == 403


def test_teacher_uploads_pdf_and_word_notes_and_the_quiz_uses_them(client):
    from tests.test_sources_files import make_docx, make_pdf
    teacher, _ = signup(client, "teacher")
    cls = client.post("/classes", json={"name": "Files"}, headers=teacher).json()
    topic = client.post(f"/classes/{cls['id']}/topics", json={"title": "Cells", "questions_per_quiz": 2},
                        headers=teacher).json()
    pdf_line = "Mitochondria release energy from glucose during cellular respiration."
    up = lambda name, data, mime: client.post(  # noqa: E731
        f"/topics/{topic['id']}/notes", files={"file": (name, data, mime)}, headers=teacher)

    r = up("cells.pdf", make_pdf([pdf_line]), "application/pdf")
    assert r.status_code == 200 and r.json()["filename"] == "cells.pdf" and r.json()["chars"] > 40
    r = up("cells.docx", make_docx(["The nucleus stores the genetic material of the cell."]),
           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert r.status_code == 200
    assert up("old.doc", b"\xd0\xcf\x11\xe0", "application/msword").status_code == 400
    assert up("huge.pdf", b"%PDF" + b"0" * (10 * 1024 * 1024), "application/pdf").status_code == 413
    notes = client.get(f"/topics/{topic['id']}", headers=teacher).json()["notes"]
    assert [n["filename"] for n in notes] == ["cells.pdf", "cells.docx"]

    student, user = signup(client, "student")
    client.post("/classes/join", json={"join_code": cls["join_code"]}, headers=student)
    teach(client, on(student, topic), pdf_line)
    run_exam(client, on(student, topic))
    detail = client.get(f"/classes/{cls['id']}/students/{user['id']}", headers=teacher).json()
    prompts = " ".join(q["prompt"] for q in detail["topics"][0]["attempts"][0]["questions"])
    assert "Mitochondria" in prompts and "nucleus" in prompts  # written from both files


def test_students_can_upload_pdf_and_word_for_free_practice(client):
    from tests.test_sources_files import make_docx, make_pdf
    s, _ = signup(client, "student")
    for name, data in (("a.pdf", make_pdf(["Recursion means a function calls itself again."])),
                       ("b.docx", make_docx(["A base case stops the recursion."]))):
        assert client.post("/sources", files={"file": (name, data)}, headers=s).status_code == 200
    assert [x["filename"] for x in client.get("/sources", headers=s).json()["sources"]] == ["a.pdf", "b.docx"]
