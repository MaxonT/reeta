"""Topics a teacher sets for a class, and the gradebook.

A topic is a title, instructions for the students, and notes (sources under 'topic:<id>') that every quiz on it
is written from. Each student teaches their own Reeta per topic, under 'user:<id>:topic:<id>' (see sessions.py).
The gradebook shows, per student, their progress on each topic, plus their free practice.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import gradebook
from .accounts import Accounts
from .service import ReetaService
from .sessions import student_topic_session, topic_notes_session, user_session
from .sources import SourceError

MAX_TITLE, MAX_INSTRUCTIONS, MAX_QUESTIONS = 200, 2000, 10


class TopicBody(BaseModel):
    title: str
    instructions: str = ""
    questions_per_quiz: int = 3


class TopicPatch(BaseModel):
    title: str | None = None
    instructions: str | None = None
    questions_per_quiz: int | None = None


def _clean_topic(title: str | None, instructions: str | None, questions: int | None) -> dict:
    """Validated fields among the ones given."""
    out = {}
    if title is not None:
        out["title"] = title.strip()
        if not out["title"] or len(out["title"]) > MAX_TITLE:
            raise HTTPException(400, "Give the topic a title (up to 200 characters).")
    if instructions is not None:
        out["instructions"] = instructions.strip()
        if len(out["instructions"]) > MAX_INSTRUCTIONS:
            raise HTTPException(400, f"Keep the instructions under {MAX_INSTRUCTIONS} characters.")
    if questions is not None:
        if not 1 <= questions <= MAX_QUESTIONS:
            raise HTTPException(400, f"A quiz has 1 to {MAX_QUESTIONS} questions.")
        out["questions_per_quiz"] = questions
    return out


class Classwork:
    def __init__(self, svc: ReetaService, accounts: Accounts, max_source_bytes: int):
        self.svc, self.repo, self.accounts = svc, svc.repo, accounts
        self.max_source_bytes = max_source_bytes
        self.router = self._routes()

    def questions_for(self, topic_id: int) -> int | None:
        topic = self.repo.get_topic(topic_id)
        return topic["questions_per_quiz"] if topic else None

    # Helpers
    def _topic(self, topic_id: int) -> tuple[dict, dict]:
        topic = self.repo.get_topic(topic_id)
        cls = topic and self.repo.get_class(topic["class_id"])
        if not cls:
            raise HTTPException(404, "Topic not found")
        return topic, cls

    def _teacher_topic(self, topic_id: int, teacher: dict) -> dict:
        topic, cls = self._topic(topic_id)
        if cls["teacher_id"] != teacher["id"]:
            raise HTTPException(404, "Topic not found")
        return topic

    def _notes(self, topic_id: int) -> list[dict]:
        return self.svc.list_sources(topic_notes_session(topic_id))

    def _progress(self, student_id: int, topic_id: int) -> tuple[dict, list[dict]]:
        session = student_topic_session(student_id, topic_id)
        rows = self.accounts.grades(session)
        taught = any((lec.get("text") or "").strip() for lec in self.repo.list_lectures(session))
        return gradebook.topic_progress(rows, taught), rows

    def _topic_out(self, topic: dict, **extra) -> dict:
        return {k: topic[k] for k in ("id", "class_id", "title", "instructions", "questions_per_quiz", "created_at")} \
            | {"notes_count": len(self._notes(topic["id"]))} | extra

    def _routes(self) -> APIRouter:
        r = APIRouter()
        teacher, student = self.accounts.role("teacher"), self.accounts.role("student")
        current = self.accounts.current_user

        # Teacher: topics
        @r.post("/classes/{class_id}/topics")
        def create_topic(class_id: int, body: TopicBody, user: dict = Depends(teacher)):
            self.accounts.teacher_class(class_id, user)
            f = _clean_topic(body.title, body.instructions, body.questions_per_quiz)
            topic_id = self.repo.create_topic(class_id, f["title"], f["instructions"], f["questions_per_quiz"])
            return self._topic_out(self.repo.get_topic(topic_id))

        @r.get("/classes/{class_id}/topics")
        def class_topics(class_id: int, user: dict = Depends(teacher)):
            self.accounts.teacher_class(class_id, user)
            return {"topics": [self._topic_out(t) for t in self.repo.list_topics(class_id)]}

        @r.patch("/topics/{topic_id}")
        def update_topic(topic_id: int, body: TopicPatch, user: dict = Depends(teacher)):
            self._teacher_topic(topic_id, user)
            self.repo.update_topic(topic_id, **_clean_topic(body.title, body.instructions, body.questions_per_quiz))
            return self._topic_out(self.repo.get_topic(topic_id))

        @r.post("/topics/{topic_id}/notes")
        async def add_notes(topic_id: int, file: UploadFile | None = File(default=None),
                            text: str | None = Form(default=None), user: dict = Depends(teacher)):
            """The material every quiz on this topic is written from. A .txt, .md, .pdf or .docx file, or pasted text."""
            self._teacher_topic(topic_id, user)
            data = None
            if file:
                data = await file.read(self.max_source_bytes + 1)
                if len(data) > self.max_source_bytes:
                    raise HTTPException(413, "That file is too large.")
            try:
                return self.svc.add_source(topic_notes_session(topic_id), file.filename if file else None, data, text)
            except SourceError as exc:
                raise HTTPException(exc.status, str(exc)) from exc

        @r.delete("/topics/{topic_id}/notes/{source_id}")
        def delete_notes(topic_id: int, source_id: int, user: dict = Depends(teacher)):
            self._teacher_topic(topic_id, user)
            if not self.svc.delete_source(topic_notes_session(topic_id), source_id):
                raise HTTPException(404, "Notes not found")
            return {"ok": True}

        # Either: one topic, for its teacher or a student in its class
        @r.get("/topics/{topic_id}")
        def get_topic(topic_id: int, user: dict = Depends(current)):
            topic, cls = self._topic(topic_id)
            if user["role"] == "teacher" and cls["teacher_id"] == user["id"]:
                return self._topic_out(topic, class_name=cls["name"], notes=self._notes(topic_id))
            if user["role"] == "student" and self.repo.is_member(cls["id"], user["id"]):
                return self._topic_out(topic, class_name=cls["name"], notes=self._notes(topic_id),
                                       progress=self._progress(user["id"], topic_id)[0])
            raise HTTPException(404, "Topic not found")

        # Student: every topic in their classes, with where they are on it
        @r.get("/me/topics")
        def my_topics(user: dict = Depends(student)):
            return {"topics": [
                self._topic_out(t, class_name=c["name"], progress=self._progress(user["id"], t["id"])[0])
                for c in self.repo.list_student_classes(user["id"]) for t in self.repo.list_topics(c["id"])]}

        # Teacher: the gradebook
        @r.get("/classes/{class_id}/gradebook")
        def class_gradebook(class_id: int, user: dict = Depends(teacher)):
            cls = self.accounts.teacher_class(class_id, user)
            topics = self.repo.list_topics(class_id)
            students = []
            for s in self.repo.list_members(class_id):
                progress, all_rows = {}, []
                for t in topics:
                    progress[str(t["id"])], rows = self._progress(s["id"], t["id"])
                    all_rows += rows
                all_rows.sort(key=lambda row: row["created_at"])
                students.append({"student": s, "summary": gradebook.summary(all_rows), "topics": progress,
                                 "practice": gradebook.summary(self.accounts.grades(user_session(s["id"])))})
            return {"class": cls, "topics": [{k: t[k] for k in ("id", "title", "questions_per_quiz")} for t in topics],
                    "students": students}

        @r.get("/classes/{class_id}/students/{student_id}")
        def student_gradebook(class_id: int, student_id: int, user: dict = Depends(teacher)):
            cls = self.accounts.teacher_class(class_id, user)
            if not self.repo.is_member(class_id, student_id):
                raise HTTPException(404, "Student not found in this class")
            topics, all_rows = [], []
            for t in self.repo.list_topics(class_id):
                progress, rows = self._progress(student_id, t["id"])
                topics.append({"topic": {"id": t["id"], "title": t["title"]}, "progress": progress, "attempts": rows})
                all_rows += rows
            all_rows.sort(key=lambda row: row["created_at"])
            practice = self.accounts.grades(user_session(student_id))
            return {"class": {k: cls[k] for k in ("id", "name")}, "student": self.repo.get_user(student_id),
                    "summary": gradebook.summary(all_rows), "topics": topics,
                    "practice": {"summary": gradebook.summary(practice), "attempts": practice}}

        return r
