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
