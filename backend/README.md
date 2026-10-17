# Reeta backend

FastAPI service that turns a spoken Lecture into a Notebook, grades the AI student's Exam with plain code, and
remembers every attempt. The frontend talks to it over HTTP only (see the main [README](../README.md#how-the-frontend-and-backend-connect)).

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                       # no network, no keys
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
   ├── persona.py        Reeta's voice: deterministic line bank and PERSONA_PROMPT for the LLM
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

## Reeta loop

A short daily loop, like Duolingo. Reeta is "the earnest dummy": she believes everything you say and repeats
your mistakes back sincerely. Her voice lives in `app/persona.py`, a deterministic line bank (no LLM needed).
`PERSONA_PROMPT` is the system prompt the OpenAI and OCI clients use to phrase lines; their output must still
contain the graded answer verbatim, or the persona line is used. Grading is still only `grading.py`.

Rounds are stored in `loop_rounds` and cleared by `POST /session/reset`. Dates use the server's local time.

**`POST /loop/quiz`** picks up to 3 Exam questions: first those on concepts confirmed in the latest Lecture, then
the weakest concepts (misconception, then missing, in Answer key order), then the rest in exam order. They are
graded with `grade_exam` on the current Notebook. `passed` means every question was correct.

```json
{
  "round_id": 1, "score": 1, "total": 3, "passed": false, "mood": "confused",
  "result_line": "1 out of 3! Almost there. Can you help me with the rest?",
  "results": [
    {"question_id": "q6", "answer": "True", "is_correct": false, "reason": "misconception",
     "concept_ids": ["independent_frames"], "citations": [{"text": "All the calls share the same variables.", "...": "..."}],
     "line": "My notes say “All the calls share the same variables”, so obviously recursion is basically roommates sharing one fridge. I picked “True”!",
     "question": {"id": "q6", "type": "true_false", "prompt": "When f(3) calls f(2), ...", "options": ["True", "False"],
                  "required_concepts": ["independent_frames"]}}
  ],
  "streak": 0
}
```

Each item in `results` has the same fields as in `POST /exam/take`.

**`GET /loop/today`** is the home screen state.

```json
{
  "streak": 3, "best_streak": 5,
  "last_round_at": "2026-10-17T09:30:00", "days_since_last": 0,
  "mood": "confused",
  "ask": {"concept_id": "independent_frames", "label": "Independent frames", "reason": "misconception"},
  "line": "I tried my best last time but something's off. Is it independent frames?",
  "progress": {"mastered": 1, "total": 5},
  "level": "Freshman"
}
```

1. `streak`: consecutive calendar days with at least one passed round, ending today or yesterday. `best_streak`
   is the longest run ever. `last_round_at` and `days_since_last` are `null` before the first round.
2. `mood`: `sad` if the last round was 2 or more days ago, else `confused` if the last round failed, else `proud`
   if a round passed today, else `listening`.
3. `ask`: the first concept holding a misconception, else the first missing one, else (`review`) the concept
   the rounds covered least recently.
4. `level`: Freshman (0 to 1 mastered), Sophomore (2), Junior (3 to 4), Graduate (5).

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
3. `test_search.py`: notebook search and concept edges
4. `test_loop.py`: daily loop question picking, streak math, mood, ask, reset, persona lines

Add a test whenever you change `grading.py` or `service.py`.

## Running on OCI GenAI

Set `LLM_PROVIDER=oci` to use Cohere Command A on Oracle OCI Generative AI (us-chicago-1). Mock stays the default,
and any OCI error falls back to the Mock. Auth comes from `~/.oci/config`.

| Variable | Default |
| --- | --- |
| `OCI_COMPARTMENT_ID` | required (falls back to the tenancy in the config) |
| `OCI_PROFILE` | `DEFAULT` |
| `OCI_CONFIG_FILE` | `~/.oci/config` |
| `OCI_GENAI_MODEL` | `cohere.command-a-03-2025` |
| `OCI_GENAI_ENDPOINT` | `https://inference.generativeai.us-chicago-1.oci.oraclecloud.com` |

Extraction output is always checked by `validate_entries` against the Answer key, same as the OpenAI client.
