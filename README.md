# Reeta

Learn by teaching your AI. HackTN26, Oracle x Vanderbilt, Challenge #3: AI That Strengthens Learning.

You are the **Professor**. You give a spoken **Lecture** on Python recursion to an **AI student** that knows
nothing except what you said. The AI student takes an **Exam**. Wherever it fails, the app shows exactly what you
never taught or taught wrong, quotes your own sentence and replays that audio clip. You go to **Office hours**,
re teach by voice, and the AI student retakes the Exam until it passes. The **Report** grades your teaching.

**Hard rule:** the AI student never uses an LLM's built in knowledge. Grading is deterministic code over the
**Notebook**. LLMs only (1) map Lecture sentences to concepts and (2) phrase the AI student's replies.

Team workflow (branches, PRs, no conflicts): see [CONTRIBUTING.md](CONTRIBUTING.md).

## Architecture

```
 Browser (React + Vite)                         Backend (FastAPI)
 ──────────────────────                         ─────────────────────────────────────────────────────────
 Lecture hall                                   POST /lectures/audio
  MediaRecorder (push to talk) ──audio────────▶  ┌────────────────┐   sentences + start_ms/end_ms
  Web Speech API (live chalk + ─transcript──▶    │ SpeechClient   │── OpenAIWhisperClient   (now)
   fallback transcript)                          │  .transcribe() │── OCISpeechClient       (stub)
                                                 └───────┬────────┘── browser transcript  (fallback)
                                                         ▼
                                                 ┌────────────────┐   {concept_id, status,
                                                 │ LLMClient      │    misconception_id} | irrelevant
                                                 │ .extract_      │── MockLLMClient  (offline, default)
                                                 │   entries()    │── OpenAIClient   (dev, falls back to Mock)
                                                 └───────┬────────┘── OCIGenAIClient (stub)
                                                         ▼            validated against Answer key ids
  Professor confirms entries ──────────────────▶ POST /lectures/{id}/confirm
                                                         ▼
 Notebook scene (React Flow concept map) ◀────── Notebook (new entry supersedes old, never deleted)
                                                         ▼
 Exam room ───────────────────────────────────▶ POST /exam/take
                                                 grading.py  (pure code, no LLM)
                                                   misconception ▶ mapped distractor + cite sentence
                                                   missing       ▶ "you never taught me" (wrong)
                                                   else          ▶ correct + cite entries
                                                 LLMClient.phrase()  (template fallback)
 Red pen grading ◀── results + sentence ids + timestamps
  click wrong answer: question + concept node + Professor sentence highlight,
  GET /lectures/{id}/audio, play [start_ms, end_ms]
 Office hours ──── re teach failed concepts ───▶ POST /lectures/audio (kind=office_hours) ▶ confirm ▶ retake
 Report card ◀──────────────────────────────── GET /report
                                                         │
                                                 ┌───────▼────────┐
                                                 │ Repository     │── SQLiteRepository  (now)
                                                 └────────────────┘── OracleRepository  (stub, Autonomous DB)
```

Providers are chosen with env vars, so OCI plugs in without touching business logic:

| Env var           | Values                         | Default  |
|-------------------|--------------------------------|----------|
| `SPEECH_PROVIDER` | `openai`, `browser`, `oci`     | `openai` |
| `LLM_PROVIDER`    | `mock`, `openai`, `oci`        | `mock`   |
| `DB_PROVIDER`     | `sqlite`, `oracle`             | `sqlite` |

If server transcription fails (no key, network), the backend uses the transcript the browser sent from the Web
Speech API. If that is missing too, the Lecture can be typed. `openai` and `oci` LLM clients fall back to the Mock.

## Where the knowledge map lives

The knowledge map is the **Notebook**: what the AI student knows, per concept, with a pointer back to the exact
sentence (and audio span) the Professor said. It is stored in SQLite (`backend/data/reeta.db`, schema in
`backend/app/repo/schema.sql`), behind the `Repository` interface so Oracle can replace it.

```
concepts (5 rows, seeded from content/answer_key.json)      misconceptions (seeded, linked to a concept)
    ▲                                                           ▲
    │ concept_id                                                │ misconception_id
notebook_entries  id, session_id, concept_id, status (correct | misconception), misconception_id,
                  sentence_id, confirmed (Professor checked it), superseded_by (newer entry for same concept)
    │ sentence_id
    ▼
sentences         id, lecture_id, idx, text, start_ms, end_ms
    │ lecture_id
    ▼
lectures          id, session_id, kind (lecture | office_hours), audio_path, text
```

1. **Current knowledge** = for each concept, the confirmed entry with `superseded_by IS NULL`
   (`ReetaService.active_notebook`). Missing concept = no such entry.
2. **History** is never deleted: re teaching in Office hours adds a new entry and points the old one at it.
3. **Read it**: `GET /notebook` returns every confirmed entry (with sentence text and timestamps) plus a per
   concept status. `GET /lectures` returns every sentence. The frontend draws the 5 nodes from `/notebook`;
   the edges between nodes are currently a fixed layout in `frontend/src/components/ConceptMap.jsx`.
4. **Not built yet**: a search endpoint (e.g. `GET /notebook/search?q=`) and storing concept edges in
   `content/answer_key.json`. Both are small additions on top of the tables above.

## Repo layout

```
content/answer_key.json   concepts, synonyms, misconception phrases (DRAFT, content teammate to review)
content/exam.json         10 questions with required_concepts + distractor_map (DRAFT)
backend/app/
  main.py                 FastAPI routes
  service.py              business logic (ingest, confirm/supersede, exam, office hours, report)
  grading.py              deterministic grading rules
  sentences.py            timed segments -> sentences with start_ms/end_ms
  speech/                 SpeechClient: OpenAI Whisper, OCI stub, browser fallback
  llm/                    LLMClient: Mock, OpenAI, OCI stub, FallbackLLMClient
  repo/                   Repository: SQLite (+ schema.sql), Oracle stub
backend/tests/            pytest: grading rules, Notebook supersede, mock extraction, timestamps
frontend/                 React + Vite game (chalkboard, notebook, red pen)
```

## Run it

```bash
cp .env.example .env            # add OPENAI_API_KEY for Whisper, or set SPEECH_PROVIDER=browser to go offline

# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api to :8000
```

Use Chrome for the demo (MediaRecorder + Web Speech API). Session is the `X-Session-Id` header (`demo` default).

## API

| Method | Path                         | Purpose                                                      |
|--------|------------------------------|--------------------------------------------------------------|
| POST   | `/lectures/audio`            | multipart `audio`, `kind`, optional `transcript` / `text` -> sentences + proposed entries |
| POST   | `/lectures/{id}/confirm`     | `{entry_ids, edits?, additions?}` -> Notebook                 |
| GET    | `/lectures`                  | all Lectures with sentences                                   |
| GET    | `/lectures/{id}/audio`       | audio file for clip playback                                  |
| GET    | `/notebook`                  | entries + per concept status (correct, misconception, missing)|
| POST   | `/exam/take`                 | graded results with citations and timestamps                  |
| GET    | `/office-hours`              | failed concepts and what the AI student asks                  |
| GET    | `/report`                    | teaching evaluation per concept                               |
| POST   | `/session/reset`             | wipe the session                                              |
| GET    | `/answer-key`                | concept labels for the UI (no answers)                        |

## Status

| Milestone | State |
|-----------|-------|
| 1. Scaffold, README, `.env.example`, `.gitignore` | done |
| 2. Backend: Whisper + MockLLMClient + SQLite + grading, pytest | done, 14 tests |
| 3. Frontend scenes wired to the API (static first) | done, all 6 scenes |
| 4. Linked highlight + audio clip replay | done (Web Audio decode, plays `[start_ms, end_ms]`) |
| 5. OCI / Oracle stubs with TODOs | done: `speech/oci_speech.py`, `llm/oci_genai.py`, `repo/oracle_repo.py` |

Browser smoke test of the whole loop: `python scripts/e2e_smoke.py` (backend with `SPEECH_PROVIDER=browser`
on :8000, `npm run dev` on :5173). Not yet verified against a real OpenAI key or a real microphone in this repo's CI.

## Demo script (2 min)

1. Lecture: "A recursive function is a function that calls itself. Recursion stops by itself. All the calls share the same variables."
2. Confirm, look at the Notebook map: 1 green, 2 red, 2 dashed gray.
3. Exam: AI student fails. Click a red answer: your sentence lights up and your own voice replays.
4. Office hours: "Correction, recursion needs a base case. Each call works on a smaller problem, n minus 1. Each call has its own stack frame. The return value passes back up to the caller."
5. Retake: 10/10. Report card.
