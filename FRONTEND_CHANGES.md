# Frontend changes needed for the new backend

The backend moved from "concept notebook + multiple choice exam" to "Reeta reads the
student's transcripts and answers open-ended questions with a quote". The UI has NOT been
changed yet. This is the list of what breaks and what to build. Written from a read of the
code (grep of `frontend/src`), not from running it, so verify each item when you get to it.

## Already changed in the backend (the UI above it is now out of date)

- `POST /lectures/audio` now returns `{lecture: {id, kind, has_audio, transcript_source, text, words}, warning}`.
  It no longer returns `sentences` or `proposed_entries`.
- `lectures` store `text` and `words: [{w, start_ms, end_ms}]`. There are no sentence rows.
- Removed tables: `concepts`, `misconceptions`, `sentences`, `notebook_entries`.

## Built on the backend (UI will need to follow)

`POST /exam/run?questions=5` (header `X-Session-Id`) replaces `POST /exam/take`. It streams
Server-Sent Events so the UI can show Reeta answering live. Questions are open-ended and written
by an LLM from the course notes (`content/answer_key.json`). Call it right after the upload resolves.
Read it with `fetch` + a stream reader (`EventSource` cannot POST). Each message is `event: <name>` then
`data: <json>`. Events, in order:

| event | data | meaning |
|---|---|---|
| `questions` | `{attempt_id, attempt_no, questions: [{id, prompt}]}` | the whole exam, sent first |
| `question_start` | `{id}` | Reeta starts on this question |
| `answer_delta` | `{id, text}` | next piece of her answer; append it (typing effect). The `QUOTE:` tail is never sent. |
| `answer_reset` | `{id}` | the backup model restarted the answer; clear the text so far |
| `answer_done` | `{id, line, supported, lecture_id, quote, quote_start_ms, quote_end_ms}` | her full answer. `quote` is checked to be real text from a lecture. `supported: false` means no valid quote. ms values are null for typed lectures. |
| `graded` | `{id, is_correct, reason, feedback}` | `reason` is `correct`, `wrong`, or `not_taught`. Arrives in question order, usually shortly after `answer_done`. |
| `done` | `{attempt_id, attempt_no, score, total, passed}` | finished |
| `error` | `{message}` | the exam could not run, or failed part way |

Notes for the UI:
- `graded.reason` can be `not_taught` even after an `answer_done` that had `supported: true`: the judge found
  the quote did not back the answer (outside knowledge). Treat the `graded` event as the final word, and clear
  the quote shown from `answer_done` when `reason` is `not_taught`.
- Open-ended answers replace multiple choice `options`. There is no `correct_answer` to show; `feedback` is the judge's line.
- The old `/exam/take`, `/notebook`, `/office-hours`, `/report`, `/answer-key` and `/lectures/{id}/confirm` routes still
  exist in the code but no longer work with the new tables.

## What breaks, by file

| File | Why it breaks | What it needs |
|---|---|---|
| `lib/api.js` | `confirm`, `notebook`, `answerKey`, `officeHours`, `report`, `takeExam` point at endpoints that are gone or changing | Remove `confirm`/`notebook`/`answerKey`. Add a streaming `runExam` (use `fetch` + `ReadableStream`; `EventSource` cannot POST). |
| `components/TeachPanel.jsx` | Reads `res.sentences` (line 41) and `res.proposed_entries` (lines 43, 55, 101), then calls `api.confirm` (line 66). The whole "confirm Reeta's notes" step is gone | After upload, show the transcript (`lecture.text`) and a "Start exam" action, or start the exam automatically. Drop the checkbox/edit/confirm UI. |
| `scenes/NotebookScene.jsx`, `components/ConceptMap.jsx` | Built entirely on `notebook.concepts` and `notebook.entries` | Remove, or repurpose to show the transcripts. |
| `scenes/ExamRoom.jsx` | Calls `api.takeExam()` and expects a finished exam object | Open the stream and render each question and Reeta's answer as it arrives (typing effect, then correct/wrong badge, then the quoted line with a play button). |
| `scenes/Grading.jsx` | Uses `exam.passed`, `notebook.concepts` (ConceptMap, line 66), and `lec.sentences` (line 72) | Show results from the stream. Highlight the quoted span in the transcript using `words` and the quote's ms range. Drop ConceptMap. |
| `scenes/OfficeHours.jsx` | Calls `api.officeHours()` and keys everything on `concept_id` | Rebuild around missed questions ("Reeta got Q3 wrong, reteach it") or remove. |
| `scenes/ReportCard.jsx` | Calls `api.report()`, which is per concept with letter grades | Rebuild around attempts and per-question results, or remove. |
| `scenes/LectureHall.jsx`, `components/AIStudent.jsx` | `moodFromNotebook(notebook?.concepts)` drives Reeta's mood | Drive mood from the exam stream (thinking, confident, confused, "you never taught me"). |
| `App.jsx` | Loads `api.notebook()` and `api.answerKey()` on start, keeps `notebook` / `answerKey` state, and has Notebook, Office hours, and Report card tabs | Remove those fetches and state, and update the tab list. |
| `lib/clip.js` | None. It only needs a lecture id and start/end ms | Reuse as is for quote playback. It already works with `quote_start_ms` / `quote_end_ms`. |
| `lib/useRecorder.js` | None | Keep. Its browser transcript is still the fallback and is still posted as `transcript`. |

## New UI to build

### 1. Source material upload (backend is built)

Goal: the user adds source material for their session, and the exam questions are written from it.
If a session has no uploaded material, the backend falls back to `content/answer_key.json`
(the default Python recursion notes), so the UI must work with zero sources too.

API (all use the `X-Session-Id` header; sources are per session):
- `POST /sources`: multipart with `file`, or form field `text` for pasted notes (`file` wins if both are sent).
  Returns `{id, filename, chars}`; pasted notes get the filename `pasted notes`.
  Errors, each with `{detail: "<message to show the user>"}`:
  - 400: empty source, or an unsupported file type
  - 413: too long. Limit is 50,000 characters per source (`MAX_SOURCE_CHARS`); a file over about 200 KB is also refused.
- `GET /sources` -> `{sources: [{id, filename, chars, created_at}]}`, oldest first, without the text.
- `DELETE /sources/{id}` -> `{ok: true}`, or 404 if it does not exist in this session.
- Several sources are combined for the exam, capped at 60,000 characters in total (`MAX_NOTES_CHARS`); any
  excess at the end is dropped without a warning. `POST /session/reset` clears the session's sources too.

Backend behaviour the UI should know:
- Supported types are `.txt` and `.md` only, plus pasted text. PDF and Word are not supported; adding another type
  is one new function in `backend/app/sources.py`. The 400 message lists the allowed types.
- Questions are written by the LLM from the uploaded text, so quality depends on the upload. A very short or
  sentence-less upload can make the exam fail with an `error` event ("no usable sentences" with the offline backup model).
- Uploaded text is treated as source material, never as instructions.

UI to build:
- An upload control: file picker (`accept=".txt,.md"`) plus a "paste notes" textarea. Show the allowed types and the
  50,000 character limit next to it.
- A list of this session's sources with a remove button, so the user can see what the exam will use.
- A clear empty state: "No notes uploaded, using the default Python recursion notes."
- Loading and error states for the upload. Show the backend's `detail` text for 400 and 413.
- Add `api.postSource`, `api.sources`, `api.deleteSource` in `lib/api.js`. `postSource` sends `FormData`, which `req()` already supports.
- Where it lives: before recording (a "Course notes" step) or a panel in `LectureHall.jsx`. Needs a decision.
- Reset: `POST /session/reset` should also clear sources. The reset button text should say so.

### 2. Live exam view (backend is built: `POST /exam/run`, event table above)

Goal: the user watches Reeta take the exam as it happens.

- `api.runExam(onEvent, questions = 5)` in `lib/api.js`: `fetch` POST with the `X-Session-Id` header, read
  `response.body.getReader()`, decode, split on a blank line (`\n\n`) between events, and parse the `event:` and
  `data:` lines. Keep the partial last chunk in a buffer between reads. Support aborting with `AbortController`
  so leaving the scene cancels the stream.
- Start the exam automatically after a lecture upload resolves, or from a "Start exam" button. Needs a decision.
- State per question: `{id, prompt, text, status, quote, quote_start_ms, quote_end_ms, lecture_id, is_correct, reason, feedback}`.
  `status` moves `waiting` -> `answering` (on `question_start`) -> `answered` (on `answer_done`) -> `graded`.
- Render:
  - all questions listed up front from the `questions` event, the current one highlighted
  - Reeta's answer appended from `answer_delta` as it arrives; clear it on `answer_reset`
  - the quote under the answer after `answer_done`, with a play button using the existing `clip.js`
    (`lecture_id`, `quote_start_ms`, `quote_end_ms`). Hide the play button when the ms values are null.
  - a correct / wrong / "never taught" badge and the `feedback` line on `graded`. Grades can arrive a little
    after the answer, and in question order.
  - a score summary on `done`
- If `answer_done.supported` is false, show "Reeta wasn't taught this" with no quote.
- Error handling: show the `error` event message and a retry button. Handle the connection dropping before `done`
  (partial results are already saved on the backend, the attempt just has a lower score).
- Reeta (`AIStudent.jsx`) animation: thinking while `answering`, speaking while text arrives, and a
  confident / confused / "I don't know" look on `graded` (`correct` / `wrong` / `not_taught`).
- The dev proxy in `vite.config.js` is a plain pass-through, so streaming should work. Check in the browser
  that events appear one by one and not all at the end. If they arrive all at once, something is buffering.

## Keep working as is

- Recording (`useRecorder.js`) and the upload call (`api.postLecture`), because the form fields are unchanged.
- Clip playback (`clip.js`, `GET /lectures/{id}/audio`).
- `api.lectures()` still works, but each lecture now has `words` instead of `sentences`.
