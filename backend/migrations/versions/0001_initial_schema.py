"""initial schema, same tables as repo/schema.sql (SQLite)

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

NOW = sa.text("(now() at time zone 'utc')")


def _created_at(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(), nullable=False, server_default=NOW)


def upgrade() -> None:
    op.create_table(
        "lectures",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False, server_default="lecture"),   # lecture | office_hours
        sa.Column("audio_path", sa.Text()),                                       # NULL for typed text
        sa.Column("text", sa.Text(), nullable=False, server_default=""),          # what Reeta reads
        sa.Column("words", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),  # [{w, start_ms, end_ms}]
        _created_at(),
    )
    op.create_index("lectures_session", "lectures", ["session_id", "id"])

    op.create_table(
        "exam_questions",  # old seeded bank, unused by the live flow
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),                             # mcq | true_false
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", JSONB(), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
    )

    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        _created_at(),
    )
    op.create_index("exam_attempts_session", "exam_attempts", ["session_id", "attempt_no"])

    op.create_table(
        "exam_answers",
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("exam_attempts.id"), primary_key=True),
        sa.Column("question_id", sa.Text(), primary_key=True),                    # q1, q2, ... within the attempt
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference_answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer", sa.Text()),                                           # NULL = never taught
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),                           # correct | wrong | not_taught
        sa.Column("feedback", sa.Text()),
        sa.Column("lecture_id", sa.Integer(), sa.ForeignKey("lectures.id")),
        sa.Column("quote", sa.Text()),
        sa.Column("quote_start_ms", sa.Integer()),
        sa.Column("quote_end_ms", sa.Integer()),
        sa.Column("line", sa.Text()),                                             # what Reeta says aloud
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),                         # file name, or "pasted notes"
        sa.Column("text", sa.Text(), nullable=False),
        _created_at(),
    )
    op.create_index("sources_session", "sources", ["session_id", "id"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),               # lowercased
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),                             # teacher | student
        sa.Column("password_hash", sa.Text(), nullable=False),                    # scrypt$<salt hex>$<hash hex>
        _created_at(),
    )

    op.create_table(
        "auth_tokens",
        sa.Column("token_hash", sa.Text(), primary_key=True),                     # sha256 of the bearer token
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),                 # unix seconds
    )

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("join_code", sa.Text(), nullable=False, unique=True),           # students type this to join
        _created_at(),
    )

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("questions_per_quiz", sa.Integer(), nullable=False, server_default="3"),
        _created_at(),
    )

    op.create_table(
        "class_members",
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        _created_at("joined_at"),
    )


def downgrade() -> None:
    for table in ("class_members", "topics", "classes", "auth_tokens", "users", "sources",
                  "exam_answers", "exam_attempts", "exam_questions", "lectures"):
        op.drop_table(table)
