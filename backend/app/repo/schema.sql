CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS misconceptions (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES concepts(id),
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS concept_edges (
    source_id TEXT NOT NULL REFERENCES concepts(id),
    target_id TEXT NOT NULL REFERENCES concepts(id),
    PRIMARY KEY (source_id, target_id)
);
CREATE TABLE IF NOT EXISTS lectures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'lecture',          -- lecture | office_hours
    audio_path TEXT,
    text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lecture_id INTEGER NOT NULL REFERENCES lectures(id),
    idx INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_ms INTEGER NOT NULL DEFAULT 0,
    end_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notebook_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    concept_id TEXT NOT NULL REFERENCES concepts(id),
    status TEXT NOT NULL,                          -- correct | misconception
    misconception_id TEXT REFERENCES misconceptions(id),
    sentence_id INTEGER NOT NULL REFERENCES sentences(id),
    confirmed INTEGER NOT NULL DEFAULT 0,
    superseded_by INTEGER REFERENCES notebook_entries(id)
);
CREATE TABLE IF NOT EXISTS exam_questions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    prompt TEXT NOT NULL,
    options TEXT NOT NULL,                         -- JSON list
    correct_answer TEXT NOT NULL,
    required_concepts TEXT NOT NULL,               -- JSON list
    distractor_map TEXT NOT NULL                   -- JSON object
);
CREATE TABLE IF NOT EXISTS exam_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL,
    score INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS exam_answers (
    attempt_id INTEGER NOT NULL REFERENCES exam_attempts(id),
    question_id TEXT NOT NULL REFERENCES exam_questions(id),
    answer TEXT,
    is_correct INTEGER NOT NULL,
    reason TEXT NOT NULL,                          -- misconception | not_taught | correct
    concept_ids TEXT NOT NULL,                     -- JSON list
    sentence_ids TEXT NOT NULL,                    -- JSON list
    line TEXT                                      -- what the AI student said
);
