-- Simplified schema: Reeta's memory is the student's transcripts.
-- Dropped: concepts, misconceptions, sentences, notebook_entries.

CREATE TABLE IF NOT EXISTS lectures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'lecture',          -- lecture | office_hours
    audio_path TEXT,                               -- file on disk, NULL for typed text
    text TEXT NOT NULL DEFAULT '',                 -- full transcript, what Reeta reads
    words TEXT NOT NULL DEFAULT '[]',              -- JSON [{w, start_ms, end_ms}] from Whisper
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS lectures_session ON lectures(session_id, id);

CREATE TABLE IF NOT EXISTS exam_questions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                            -- mcq | true_false
    prompt TEXT NOT NULL,
    options TEXT NOT NULL,                         -- JSON list
    correct_answer TEXT NOT NULL                   -- must be one of options
);

CREATE TABLE IF NOT EXISTS exam_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,              -- set after all answers are graded
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Questions are LLM-generated per attempt, so each answer row keeps its own prompt and
-- reference answer. The exam_questions table above is the old seeded bank, unused by the live flow.
CREATE TABLE IF NOT EXISTS exam_answers (
    attempt_id INTEGER NOT NULL REFERENCES exam_attempts(id),
    question_id TEXT NOT NULL,                     -- q1, q2, ... within the attempt
    prompt TEXT NOT NULL DEFAULT '',
    reference_answer TEXT NOT NULL DEFAULT '',     -- written from the course notes
    answer TEXT,                                   -- NULL = never taught
    is_correct INTEGER NOT NULL,
    reason TEXT NOT NULL,                          -- correct | wrong | not_taught
    feedback TEXT,                                 -- judge's one line
    lecture_id INTEGER REFERENCES lectures(id),    -- recording the quote came from
    quote TEXT,                                    -- verified to appear in that transcript
    quote_start_ms INTEGER,                        -- for playing the clip back
    quote_end_ms INTEGER,
    line TEXT,                                     -- what Reeta says aloud
    PRIMARY KEY (attempt_id, question_id)
);

-- Source material a session uploads. Exam questions are written from it (default notes if none).
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    filename TEXT NOT NULL,                        -- file name, or "pasted notes"
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS sources_session ON sources(session_id, id);

-- Accounts. A logged in user's lectures, sources and attempts use session_id 'user:<id>'.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,                    -- lowercased
    name TEXT NOT NULL,
    role TEXT NOT NULL,                            -- teacher | student
    password_hash TEXT NOT NULL,                   -- scrypt$<salt hex>$<hash hex>
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,                   -- sha256 of the bearer token, the token itself is never stored
    user_id INTEGER NOT NULL REFERENCES users(id),
    expires_at INTEGER NOT NULL                    -- unix seconds
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    join_code TEXT NOT NULL UNIQUE,                -- students type this to join
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    title TEXT NOT NULL,
    instructions TEXT NOT NULL DEFAULT '',         -- what the teacher wants covered, shown to students
    questions_per_quiz INTEGER NOT NULL DEFAULT 3,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- A topic's notes are rows in `sources` with session_id 'topic:<id>'. A student's work on it (lectures,
-- attempts) uses session_id 'user:<student id>:topic:<id>', so each topic has its own Reeta. See sessions.py.

CREATE TABLE IF NOT EXISTS class_members (
    class_id INTEGER NOT NULL REFERENCES classes(id),
    student_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (class_id, student_id)
);
