# Reeta backend

FastAPI service that turns a spoken Lecture into a Notebook, grades the AI student's Exam with plain code, and
remembers every attempt. The frontend talks to it over HTTP only (see the main [README](../README.md#how-the-frontend-and-backend-connect)).

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                       # 14 tests, no network, no keys
uvicorn app.main:app --reload --port 8000 # http://localhost:8000/docs for the interactive API
```

Settings come from `.env` at the repo root (copy `.env.example`). No key? Use `SPEECH_PROVIDER=browser` and the
default `LLM_PROVIDER=mock`, and everything runs offline. Use `python -m pytest`, not bare `pytest`: a `pytest`
on your PATH may belong to a different Python than the one you installed into.

## How it is built

Three layers. Each layer only talks to the one below it through an interface, so a provider can be swapped by
changing an env var.

```
main.py        HTTP routes. Reads the X-Session-Id header, validates input, calls the service. No logic.
   │
service.py     ReetaService: the game rules (ingest, confirm, exam, office hours, report).
   │           Knows nothing about OpenAI, OCI, SQLite or Oracle.
   ├── grading.py        pure functions, the only place answers are decided
   ├── sentences.py      timed segments -> sentences with start_ms / end_ms
   ├── content.py        loads and validates content/answer_key.json and content/exam.json
   │
   ├── speech/  SpeechClient.transcribe(audio_path) -> [{idx, text, start_ms, end_ms}]
   │      openai_whisper.py   OpenAIWhisperClient    SPEECH_PROVIDER=openai (default)
   │      base.py             BrowserSpeechClient    SPEECH_PROVIDER=browser (use the frontend transcript)
   │      oci_speech.py       OCISpeechClient        SPEECH_PROVIDER=oci (stub, TODO)
   │
   ├── llm/     LLMClient.extract_entries(...) and LLMClient.phrase(...)
   │      mock.py             MockLLMClient          LLM_PROVIDER=mock (default, synonym matching)
   │      openai_client.py    OpenAIClient           LLM_PROVIDER=openai (falls back to Mock on error)
   │      oci_genai.py        OCIGenAIClient         LLM_PROVIDER=oci (stub, falls back to Mock)
   │
   └── repo/    Repository: lectures, sentences, notebook entries, exam attempts
          sqlite_repo.py      SQLiteRepository       DB_PROVIDER=sqlite (default, backend/data/reeta.db)
          oracle_repo.py      OracleRepository       DB_PROVIDER=oracle (stub, TODO)
          schema.sql          table definitions
```

To add a provider (for example OCI): implement the abstract class in that folder's `base.py`, then add one
branch to its `get_*_client` / `get_repository` factory. Nothing in `service.py` changes.

## What happens on each request

**1. A Lecture comes in** (`POST /lectures/audio`, `ReetaService.ingest_lecture`)

1. Save the audio to `backend/data/audio/lecture_<id>.<ext>`.
2. Get sentences, first source that works wins: server transcription (Whisper), then the browser's Web Speech
   transcript, then typed text. The response says which one in `transcript_source`.
3. `LLMClient.extract_entries` maps sentences to concept ids. `llm/base.py: validate_entries` drops anything
   whose ids are not in the Answer key, so a confused LLM cannot invent concepts.
4. Store the proposed entries as **unconfirmed**. Nothing reaches the Notebook yet.

**2. The Professor confirms** (`POST /lectures/{id}/confirm`, `ReetaService.confirm`)

The Professor can tick, edit or add entries. Each confirmed entry becomes the current knowledge for its concept.
The previous entry is not deleted; it gets `superseded_by` pointing at the new one. That is how Office hours
"fixes" a concept while the Report can still show the history.

**3. The Exam** (`POST /exam/take`, `grading.py`)

For every question, using only the current Notebook:

1. a required concept holds a misconception: wrong, pick the distractor mapped to that misconception, cite the
   Professor's sentence (with `start_ms` / `end_ms` for clip replay)
2. else a required concept is missing: wrong, "you never taught me"
3. else: correct, cite the entries used

Only after grading does `LLMClient.phrase` word the AI student's reply. If it fails, `template_phrase` is used.
The LLM never changes `answer` or `is_correct`.

**4. Office hours and Report** (`GET /office-hours`, `GET /report`)

Office hours lists only the concepts failed in the last attempt, with what the AI student asks. The Report gives
each concept a grade: A taught right first time, B fixed in Office hours, D still a misconception, F never taught.

## Data

Content is read once at startup from `content/` and seeded into the database. Concept and misconception ids are
the contract between `answer_key.json`, `exam.json`, the database and the frontend: renaming one means updating
all of them.

The Notebook tables and how "current knowledge" is computed are described in the main README under
[Where the knowledge map lives](../README.md#where-the-knowledge-map-lives). `backend/data/` is gitignored.

## Tests

`backend/tests/` uses an in memory SQLite database and the Mock LLM, so it needs no network:

1. `test_grading.py`: the three grading rules and citations
2. `test_notebook.py`: confirm, supersede, office hours, mock extraction, sentence timestamps

Add a test whenever you change `grading.py` or `service.py`.
