# Reeta frontend

React 18 + Vite single page app. The default view is the **daily loop**: phone sized screens (Home, Course
notes, Teach, Quiz, Result) where you teach Reeta, the AI student, and watch her take a live 5 question exam.
The app holds no secrets and no game rules: every decision (what the questions are, what Reeta answers, which
answers are right) comes from the backend over `/api`.

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

1. **Home.** Reeta in her current mood, her line, the streak flame and the last quiz score. A "Course notes"
   button shows which notes the quiz is written from, and one big button: Teach Reeta. The streak and last
   score live in `localStorage` per session (`lib/loopState.js`); the backend does not keep them.
2. **Course notes.** Upload `.txt` / `.md` or paste notes (`POST /sources`, up to 50,000 characters), see the
   list (`GET /sources`) and remove one (`DELETE /sources/{id}`). With no notes the backend uses the default
   Python recursion notes. Upload errors show the backend's own `detail` text.
3. **Teach.** Hold the mic button (or Space) to talk, up to 60 seconds on the ring timer, or "Type instead".
   `POST /lectures/audio`, then Reeta shows what she wrote down (`lecture.text`). There is no confirm step.
4. **Quiz.** The live exam, `POST /exam/run?questions=5`, read as Server-Sent Events with `fetch` (see
   `api.runExam`). All questions are listed first. Reeta types each answer as it streams in, then each one is
   graded: correct, wrong, or never taught. Under the answer, the exact words of your lecture she relied on are
   highlighted (by word timings for recordings, by text match for typed lessons), with a replay button when
   there is a recording. Leaving the screen aborts the stream.
5. **Result.** A pass gets the proud face, confetti and streak +1. A fail lists what she got wrong, with "Fix it"
   (back to Teach with `kind=office_hours` on the first wrong question) and "Done for today".

The old six scene classroom (`ClassroomApp.jsx`, at `#classroom`) is built on endpoints the new backend no
longer supports, so it has no link on Home.

### Demo script

Run the backend with `LLM_PROVIDER=mock` for a repeatable demo (a real LLM writes different questions). Open
**http://localhost:5173/#demo**: it resets the session (lectures, notes, attempts) and the local streak. With
the default notes the 5 questions are the five recursion concepts (self call, base case, smaller problem,
independent frames, return propagation). Then on stage:

1. Teach Reeta, **record** so replay works: "A recursive function calls itself. Each call works on a smaller
   problem. Recursion stops by itself when it is done. Each call has its own local variables. The return value
   passes back up to the caller."
2. Quiz: 4/5. The base case answer is wrong, and "Because you said" highlights "Recursion stops by itself when
   it is done." in your lecture, with your voice on replay.
3. Fix it, record: "Recursion needs a base case where it stops, otherwise it recurses forever."
4. Quiz: 5/5, confetti, streak +1.

Other subjects: `demo/notes/` has Biology and Economics notes with lesson scripts. They need a real LLM; the
mock only turns note sentences into template questions.

Open `#demo` again to reset before the next run.

## How it is built

```
src/
  main.jsx               mounts <App />
  App.jsx                picks the view: daily loop (default) or classroom (#classroom)
  ClassroomApp.jsx       the six scene classroom and its shared state (answerKey, notebook, lectures, exam)
  loop/
    Loop.jsx             daily loop screen switcher and shared state; #demo handling
    Home.jsx, Notes.jsx, Teach.jsx, Quiz.jsx, Result.jsx   the screens
    Reeta.jsx            Reeta's face (public/teachback) and speech bubble
    ui.jsx               streak flame and top bar
    loop.css             loop styles, scoped under .lp-app (DM Sans, one green accent)
  styles.css             all styles (chalkboard, notebook paper, red pen)
  lib/
    api.js               the only file that calls fetch: one function per backend endpoint
    useRecorder.js       push to talk hook: MediaRecorder audio + Web Speech live transcript
    clip.js              plays one sentence of the Professor's recording ([start_ms, end_ms])
    loopState.js         streak and last quiz result in localStorage
    reetaLines.js        Reeta's fixed UI lines (recording, processing, quiz)
    demoSeed.js          the #demo reset
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
| Loop Home / Notes | `GET /sources`, `POST /sources`, `DELETE /sources/{id}` | which notes the quiz uses |
| Loop Teach        | `POST /lectures/audio` | what Reeta wrote down |
| Loop Quiz         | `POST /exam/run` (stream), `GET /lectures`, `GET /lectures/{id}/audio` (in `clip.js`) | live answers, grades, your highlighted words and voice |
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
