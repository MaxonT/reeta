# React integration

These files are for an existing React + TypeScript project. No API key, backend, or additional UI library is required for the components.

1. Copy `TeachbackClassroom.tsx` and `teachback.css` into `src/components/teachback/`.
2. Copy the four `student-*.svg` files from the kit into `public/teachback/`. Or pass `assetBase` for your own public URL prefix.
3. Import and render the component as shown below. `Example.tsx` is an optional visual fixture; it logs callback instructions to the console and does not record or grade.

```tsx
import TeachbackClassroom from './components/teachback/TeachbackClassroom';

<TeachbackClassroom
  phase={phase}
  topic="Python recursion"
  code={lessonCode}
  sentences={lectureSentences}
  notes={notebookEntries}
  questions={gradedQuestions}
  notebookReady={notebookReady}
  passed={gradingResult?.passed}
  recordingTime={recordingTime}
  errorMessage={errorMessage}
  onStartLecture={startRecording}
  onStopLecture={stopRecordingAndTranscribe}
  onTakeExam={runExam}
  onReteach={startNewAttempt}
  onRetry={retryLastOperation}
/>
```

## Connect the five handlers

- `onStartLecture`: request microphone access and begin your existing MediaRecorder/voice implementation; set phase to `recording` only after success. Clear stale exam results when a new attempt begins.
- `onStopLecture`: stop and retain the recording, set `transcribing`, submit audio to the team's Whisper pipeline, and store exact original transcript sentences with stable IDs, attempt numbers and timestamps. Set `notebookReady=false` until extraction finishes. Set `ready` after the notebook is stored.
- `onTakeExam`: set `testing`, call your team's deterministic grader, store its questions, evidence IDs and explicit pass result, then set `review`. Never calculate answers in this UI.
- `onReteach`: preserve previous sentences/notes and start a new attempt; clear the old result and set `notebookReady=false` for the new attempt. You may filter displayed data to an attempt, but IDs must stay unique across attempts.
- `onRetry`: retry the failed operation using retained audio/input, without erasing the previous valid notebook. Set phase to `error` and provide a readable message on failure.

Use controlled parent state: the component never creates scores or marks a student as passed. All data shapes are exported in `TeachbackClassroom.tsx`. Question and note evidence must reference stored IDs. Empty source IDs are supported and display “Not covered in your lecture.” A crossed-out draft and margin comment are optional presentation fields; omit them unless your application has an explicit draft/comment to show.

## Fonts and white chalk

All chalkboard writing and the chalk stick are pure white `#FFFFFF`. Highlighted evidence switches to dark ink on amber so the selected text stays readable. Python uses IBM Plex Mono. The Lighthouse heading currently resolves only if installed locally; Patrick Hand is the fallback. Once the exact licensed webfont is supplied, put it in your public font directory and replace the font-face source:

```css
@font-face {
  font-family: Lighthouse;
  src: url('/fonts/lighthouse.woff2') format('woff2');
  font-display: swap;
}
```

No Lighthouse binary is included. The other fonts use Google Fonts with system fallbacks. Self-host them if required by your deployment. The CSS is scoped to `.teachback` and does not restyle the rest of your app.

## Accessibility / behavior

Buttons are keyboard accessible and at least 44px tall. Source tracing highlights the question, associated notes, and exact original sentences together, then scrolls the classroom into view. Status messages announce the selected evidence. Errors use an alert. Color is paired with labels and check/cross symbols. Reduced motion uses immediate scrolling. The eraser and dust are decorative CSS and ignored by assistive technology.
