# Reeta frontend

React 18 + Vite single page game. Six scenes, one per step of the teaching loop. It holds no secrets and no game
rules: every decision (what the AI student knows, which answers are right) comes from the backend over `/api`.

## Run

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, needs the backend on :8000
npm run build    # production build into dist/, run this before every PR
```

Use Chrome: push to talk needs `MediaRecorder` and the live chalk transcript needs the Web Speech API. If the
backend is not running, a banner tells you how to start it. Point the proxy at another backend with
`VITE_API_TARGET=http://host:port npm run dev`.

## How it is built

```
src/
  main.jsx               mounts <App />
  App.jsx                scene switcher and shared state (answerKey, notebook, lectures, exam)
  styles.css             all styles (chalkboard, notebook paper, red pen)
  lib/
    api.js               the only file that calls fetch: one function per backend endpoint
    useRecorder.js       push to talk hook: MediaRecorder audio + Web Speech live transcript
    clip.js              plays one sentence of the Professor's recording ([start_ms, end_ms])
  components/
    TeachPanel.jsx       chalkboard: record or type, upload, then confirm the AI student's notes
    ConceptMap.jsx       React Flow map of the 5 concepts, colored by Notebook status
    AIStudent.jsx        the animated AI student with a speech bubble
  scenes/
    LectureHall.jsx      1. teach by voice (TeachPanel kind="lecture")
    NotebookScene.jsx    2. what the AI student learned (ConceptMap)
    ExamRoom.jsx         3. AI student takes the Exam, answers revealed one by one
    Grading.jsx          4. red pen: click a wrong answer to highlight the concept and replay your sentence
    OfficeHours.jsx      5. re teach only the failed concepts (TeachPanel kind="office_hours")
    ReportCard.jsx       6. grade per concept and attempt history
```

**State lives in `App.jsx`.** Scenes get it as props and call back (`onConfirmed`, `retake`, `go`, `onReset`)
instead of fetching on their own, so every scene sees the same Notebook. The only exceptions are
`OfficeHours` and `ReportCard`, which load their own data when opened.

**Scenes never call `fetch` directly.** Add a backend call to `lib/api.js` first, then use it.

## Which scene calls what

| Scene / component | Backend call (via `lib/api.js`) | What it shows |
|-------------------|---------------------------------|---------------|
| App (on load)     | `GET /answer-key`, `GET /notebook`, `GET /lectures` | concept labels, current Notebook |
| TeachPanel        | `POST /lectures/audio`, then `POST /lectures/{id}/confirm` | proposed notes, then the updated Notebook |
| NotebookScene     | uses `notebook` from App | 5 nodes: green correct, red misconception, gray never taught |
| ExamRoom          | `POST /exam/take` | answers and the AI student's lines |
| Grading           | `GET /lectures/{id}/audio` (in `clip.js`) | highlights + your own voice |
| OfficeHours       | `GET /office-hours` | the AI student's questions about failed concepts |
| ReportCard        | `GET /report` | grades A, B, D, F per concept |
| Reset button      | `POST /session/reset` | back to an empty Notebook |

## Two tricky parts

1. **Recording** (`useRecorder.js`). While you hold Space or the button, `MediaRecorder` records audio for the
   backend's Whisper, and the Web Speech API runs in parallel to write chalk live. Its final results are sent
   too, with timestamps relative to the start of the recording, so the backend has a transcript even if Whisper
   fails.
2. **Clip replay** (`clip.js`). Browser recorded webm files often cannot seek, so `<audio>` with a start time is
   unreliable. Instead the whole Lecture is fetched once, decoded with Web Audio, cached, and only
   `[start_ms, end_ms]` of the buffer is played.

## Session

`api.js` sends `X-Session-Id` on every request, read from `localStorage.reeta_session` (default `demo`). To give
two people separate games on one backend, set a different value in each browser:
`localStorage.setItem('reeta_session', 'alice')` and reload.
