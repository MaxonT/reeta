-- Oracle Autonomous Database (23ai) version of schema.sql.
-- Statements are separated by a line containing only "/" so the repo can run them one by one.
-- Oracle stores '' as NULL, so text columns are nullable and the repo maps None back to ''.

CREATE TABLE IF NOT EXISTS concepts (
    id          VARCHAR2(100) PRIMARY KEY,
    label       VARCHAR2(500) NOT NULL,
    description CLOB NOT NULL
)
/
CREATE TABLE IF NOT EXISTS misconceptions (
    id          VARCHAR2(100) PRIMARY KEY,
    concept_id  VARCHAR2(100) NOT NULL REFERENCES concepts(id),
    description CLOB NOT NULL
)
/
CREATE TABLE IF NOT EXISTS concept_edges (
    source_id VARCHAR2(100) NOT NULL REFERENCES concepts(id),
    target_id VARCHAR2(100) NOT NULL REFERENCES concepts(id),
    PRIMARY KEY (source_id, target_id)
)
/
CREATE TABLE IF NOT EXISTS lectures (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  VARCHAR2(200) NOT NULL,
    kind        VARCHAR2(30) DEFAULT 'lecture' NOT NULL,
    audio_path  VARCHAR2(1000),
    text        CLOB,
    words       CLOB DEFAULT '[]' NOT NULL CHECK (words IS JSON),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
)
/
CREATE INDEX IF NOT EXISTS lectures_session ON lectures(session_id, id)
/
CREATE TABLE IF NOT EXISTS exam_questions (
    id             VARCHAR2(100) PRIMARY KEY,
    type           VARCHAR2(30) NOT NULL,
    prompt         CLOB NOT NULL,
    options        CLOB NOT NULL CHECK (options IS JSON),
    correct_answer CLOB NOT NULL
)
/
CREATE TABLE IF NOT EXISTS exam_attempts (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  VARCHAR2(200) NOT NULL,
    attempt_no  NUMBER NOT NULL,
    score       NUMBER DEFAULT 0 NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
)
/
CREATE TABLE IF NOT EXISTS exam_answers (
    attempt_id       NUMBER NOT NULL REFERENCES exam_attempts(id),
    question_id      VARCHAR2(100) NOT NULL,
    prompt           CLOB,
    reference_answer CLOB,
    answer           CLOB,
    is_correct       NUMBER(1) NOT NULL,
    reason           VARCHAR2(30) NOT NULL,
    feedback         CLOB,
    lecture_id       NUMBER REFERENCES lectures(id),
    quote            CLOB,
    quote_start_ms   NUMBER,
    quote_end_ms     NUMBER,
    line             CLOB,
    PRIMARY KEY (attempt_id, question_id)
)
/
CREATE TABLE IF NOT EXISTS sources (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  VARCHAR2(200) NOT NULL,
    filename    VARCHAR2(500) NOT NULL,
    text        CLOB,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
)
/
CREATE INDEX IF NOT EXISTS sources_session ON sources(session_id, id)
/
CREATE TABLE IF NOT EXISTS loop_rounds (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  VARCHAR2(200) NOT NULL,
    created_at  VARCHAR2(40) NOT NULL,                   -- ISO 8601 text, as the interface passes it
    lecture_id  NUMBER REFERENCES lectures(id),
    score       NUMBER NOT NULL,
    total       NUMBER NOT NULL,
    passed      NUMBER(1) NOT NULL,
    concept_ids CLOB NOT NULL CHECK (concept_ids IS JSON)
)
/
