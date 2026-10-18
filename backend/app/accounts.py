"""Teacher and student accounts and classes. Topics and the gradebook are in classwork.py.

A logged in user's data lives under session_id 'user:<id>', and a student's work on a topic under
'user:<id>:topic:<id>' (sent as X-Topic-Id), so ReetaService works unchanged (see sessions.py). Requests without
a token keep the old X-Session-Id header (default 'demo'), but may not name a reserved session.
Passwords are scrypt hashed; bearer tokens are random and only their sha256 is stored.
"""
import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from . import gradebook
from .repo.base import Repository
from .sessions import is_reserved, student_topic_session, user_session

ROLES = ("teacher", "student")
TOKEN_TTL_S = 30 * 24 * 3600
MIN_PASSWORD = 8
_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT).hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, want = stored.split("$")
    except ValueError:
        return False
    got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT).hex()
    return scheme == "scrypt" and hmac.compare_digest(got, want)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SignupBody(BaseModel):
    email: str
    name: str
    password: str
    role: str


class LoginBody(BaseModel):
    email: str
    password: str


class ClassBody(BaseModel):
    name: str


class JoinBody(BaseModel):
    join_code: str


class Accounts:
    def __init__(self, repo: Repository, pass_threshold: float):
        self.repo = repo
        self.pass_threshold = pass_threshold

        # FastAPI dependencies. Closures, so FastAPI never sees a `self` parameter.
        def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
            if not authorization:
                return None
            scheme, _, token = authorization.partition(" ")
            user = repo.user_for_token(_token_hash(token.strip()), int(time.time())) \
                if scheme.lower() == "bearer" and token.strip() else None
            if not user:
                raise HTTPException(401, "Your login has expired. Log in again.")
            return user

        def current_user(user: dict | None = Depends(optional_user)) -> dict:
            if not user:
                raise HTTPException(401, "Log in first.")
            return user

        def session_id(user: dict | None = Depends(optional_user), x_session_id: str = Header(default="demo"),
                       x_topic_id: int | None = Header(default=None)) -> str:
            """The data session for this request: a student's topic, the account's free practice, else the
            anonymous header session."""
            if x_topic_id is not None:
                if not user:
                    raise HTTPException(401, "Log in to work on a topic.")
                if user["role"] != "student":
                    raise HTTPException(403, "Only students teach Reeta a topic.")
                topic = repo.get_topic(x_topic_id)
                if not topic or not repo.is_member(topic["class_id"], user["id"]):
                    raise HTTPException(404, "Topic not found")
                return student_topic_session(user["id"], x_topic_id)
            if user:
                return user_session(user["id"])
            if is_reserved(x_session_id):
                raise HTTPException(401, "Log in to use an account.")
            return x_session_id

        self.optional_user, self.current_user, self.session_id = optional_user, current_user, session_id
        self.router = self._routes()

    def role(self, role: str):
        """Dependency: the logged in user, who must have this role."""
        def dep(user: dict = Depends(self.current_user)) -> dict:
            if user["role"] != role:
                raise HTTPException(403, f"Only a {role} can do that.")
            return user
        return dep

    # Helpers
    def _login(self, user: dict) -> dict:
        token = secrets.token_urlsafe(32)
        self.repo.create_token(_token_hash(token), user["id"], int(time.time()) + TOKEN_TTL_S)
        return {"token": token, "user": {k: user[k] for k in ("id", "email", "name", "role")}}

    def teacher_class(self, class_id: int, teacher: dict) -> dict:
        cls = self.repo.get_class(class_id)
        if not cls or cls["teacher_id"] != teacher["id"]:  # same answer for someone else's class: no probing
            raise HTTPException(404, "Class not found")
        return cls

    def grades(self, session_id: str) -> list[dict]:
        return gradebook.gradebook(self.repo.list_attempts(session_id), self.pass_threshold)

    def _routes(self) -> APIRouter:
        r = APIRouter()
        teacher, student = self.role("teacher"), self.role("student")

        @r.post("/auth/signup")
        def signup(body: SignupBody):
            email, name = body.email.strip().lower(), body.name.strip()
            if "@" not in email or len(email) > 320:
                raise HTTPException(400, "Enter a valid email.")
            if not name or len(name) > 200:
                raise HTTPException(400, "Enter your name.")
            if body.role not in ROLES:
                raise HTTPException(400, "Pick teacher or student.")
            if len(body.password) < MIN_PASSWORD:
                raise HTTPException(400, f"Use a password of at least {MIN_PASSWORD} characters.")
            user_id = self.repo.create_user(email, name, body.role, hash_password(body.password))
            if user_id is None:
                raise HTTPException(409, "That email already has an account. Log in instead.")
            return self._login(self.repo.get_user(user_id))

        @r.post("/auth/login")
        def login(body: LoginBody):
            user = self.repo.get_user_by_email(body.email.strip().lower())
            if not user or not check_password(body.password, user["password_hash"]):
                raise HTTPException(401, "Wrong email or password.")
            return self._login(user)

        @r.post("/auth/logout")
        def logout(authorization: str | None = Header(default=None)):
            token = (authorization or "").partition(" ")[2].strip()
            if token:
                self.repo.delete_token(_token_hash(token))
            return {"ok": True}

        @r.get("/auth/me")
        def me(user: dict = Depends(self.current_user)):
            classes = (self.repo.list_teacher_classes(user["id"]) if user["role"] == "teacher"
                       else self.repo.list_student_classes(user["id"]))
            return {"user": user, "classes": classes}

        @r.get("/me/progress")
        def my_progress(user: dict = Depends(student)):
            """The student's free practice summary, so the streak survives a new browser."""
            return gradebook.summary(self.grades(user_session(user["id"])))

        @r.post("/classes")
        def create_class(body: ClassBody, user: dict = Depends(teacher)):
            name = body.name.strip()
            if not name or len(name) > 200:
                raise HTTPException(400, "Give the class a name.")
            for _ in range(10):  # a code collision is rare, just draw again
                code = "".join(secrets.choice(_CODE_CHARS) for _ in range(6))
                class_id = self.repo.create_class(user["id"], name, code)
                if class_id is not None:
                    return self.repo.get_class(class_id) | {"student_count": 0}
            raise HTTPException(500, "Could not make a join code. Try again.")

        @r.post("/classes/join")
        def join_class(body: JoinBody, user: dict = Depends(student)):
            cls = self.repo.class_by_code(body.join_code.strip().upper())
            if not cls:
                raise HTTPException(404, "No class has that code.")
            self.repo.add_member(cls["id"], user["id"])  # joining twice is fine
            return {k: cls[k] for k in ("id", "name", "join_code")}

        return r
