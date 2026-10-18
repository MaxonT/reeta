# Reeta frontend

React 18 + Vite single page app. The default view is the **daily loop**: four phone sized screens (Home, Teach,
Quiz, Result) where you teach Reeta, the AI student, and she takes a 3 question quiz. The older six scene
**Classroom view** is unchanged behind a small link on Home (or `#classroom`). The app holds no secrets and no
game rules: every decision (what Reeta knows, which answers are right) comes from the backend over `/api`.

## Run

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, needs the backend on :8000
npm run build    # production build into dist/, run this before every PR
```

Run the backend with browser speech, or recording hangs waiting for OpenAI:
`cd backend && SPEECH_PROVIDER=browser LLM_PROVIDER=mock uvicorn app.main:app --port 8000`.

Use Chrome: push to talk needs `MediaRecorder` and the live chalk transcript needs the Web Speech API. If the
backend is not running, a banner tells you how to start it. Point the proxy at another backend with
`VITE_API_TARGET=http://host:port npm run dev`.

## The daily loop

1. **Home.** Reeta in her current mood, her line from `GET /loop/today`, the streak flame, her level and 5
   concept dots. One button: Teach Reeta.
2. **Teach.** Hold the mic button (or Space) to talk, up to 60 seconds on the ring timer, or "Type instead".
   After `POST /lectures/audio` every proposed note is confirmed automatically (`POST /lectures/{id}/confirm`
   with all entry ids), because Reeta believes everything you say. Her notes appear one card at a time.
3. **Quiz.** `POST /loop/quiz`, up to 3 cards revealed one by one. A wrong answer shows "Because you said" with
   your own sentence and a replay button. The button is gray for a typed lesson, which has no audio.
4. **Result.** A pass gets the proud face, confetti and streak +1. A fail gets the confused face, "Fix it"
   (back to Teach with `kind=office_hours` on the first concept she got wrong) and "Done for today".

If `/loop/quiz` or `/loop/today` fails, `lib/loopFallback.js` falls back to `/exam/take` and `/notebook`.

### Demo script

Open **http://localhost:5173/#demo**. It resets the session and quietly teaches Reeta the background (base
case, smaller problem, return propagation, see `lib/demoSeed.js`), then shows Home. Then on stage:

1. Teach Reeta, **record** (not type, so replay works): "A recursive function calls itself. All calls share the
   same variables."
2. Quiz: 2/3. The frames question is wrong and shows "Because you said: All calls share the same variables",
   with your voice on replay.
3. Fix it, record: "Each call has its own local variables in its own stack frame."
4. Quiz: 3/3, confetti, streak +1.

Open `#demo` again to reset before the next run.

## How it is built

```
src/
  main.jsx               mounts <App />
  App.jsx                picks the view: daily loop (default) or classroom (#classroom)
  ClassroomApp.jsx       the six scene classroom and its shared state (answerKey, notebook, lectures, exam)
  loop/
    Loop.jsx             daily loop screen switcher and shared state; #demo handling
    Home.jsx, Teach.jsx, Quiz.jsx, Result.jsx   the four screens
    Reeta.jsx            Reeta's face (public/teachback) and speech bubble
    ui.jsx               streak, level, top bar, progress dots
    loop.css             loop styles, scoped under .lp-app (DM Sans, one green accent)
  styles.css             all styles (chalkboard, notebook paper, red pen)
  lib/
    api.js               the only file that calls fetch: one function per backend endpoint
    useRecorder.js       push to talk hook: MediaRecorder audio + Web Speech live transcript
    clip.js              plays one sentence of the Professor's recording ([start_ms, end_ms])
    loopFallback.js      loop data from /exam/take and /notebook when /loop/* is unavailable
    reetaLines.js        Reeta's fixed UI lines (recording, processing, quiz)
    demoSeed.js          the #demo reset and background lesson
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

**Classroom state lives in `ClassroomApp.jsx`, loop state in `loop/Loop.jsx`.** Scenes get it as props and call back (`onConfirmed`, `retake`, `go`, `onReset`)
instead of fetching on their own, so every scene sees the same Notebook. The only exceptions are
`OfficeHours` and `ReportCard`, which load their own data when opened.

**Scenes never call `fetch` directly.** Add a backend call to `lib/api.js` first, then use it.

## Which scene calls what

| Scene / component | Backend call (via `lib/api.js`) | What it shows |
|-------------------|---------------------------------|---------------|
| Loop Home         | `GET /loop/today` | mood, line, streak, level, progress |
| Loop Teach        | `POST /lectures/audio`, then `POST /lectures/{id}/confirm` (all entries) | Reeta's notes |
| Loop Quiz         | `POST /loop/quiz`, `GET /lectures/{id}/audio` (in `clip.js`) | 3 answers, your sentence and voice |
| ClassroomApp (on load) | `GET /answer-key`, `GET /notebook`, `GET /lectures` | concept labels, current Notebook |
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
