# Teachback visual handoff — Semi

Open visual-handoff.html in a browser. Keep the CSS and four SVGs beside it. Fonts load from Google Fonts when available; system fallbacks work offline.

This is a visual reference, not the functional React frontend. Working title: Teachback.

## React handoff
- Import tokens-and-styles.css; scope the global layout rules to your classroom route.
- Use student-{listening|thinking|confused|proud}.svg as image assets. All four share a 200×200 viewBox and transparent background.
- Suggested components: ClassroomShell, Chalkboard, VoiceControls, TranscriptSentence, StudentAvatar, NotebookEntry, ExamQuestion, EvidenceReview.
- Keep evidence state in a shared parent: selectedQuestionId. Resolve question → note IDs → sentence IDs using stored references. Do not match by array position or approximate text.
- Suggested evidence record: { questionId, noteIds: [], sentenceIds: [], reason, status }. Keep original sentence text and recording timestamps unchanged.
- A missing concept can have empty source IDs. Display “Not covered in your lecture”; do not claim that a nearby sentence is exact evidence.
- Student expressions: listening while recording, thinking while processing/testing, confused for a selected failed answer, proud only after a backend-confirmed pass. Idle uses listening without motion. Disable exam actions until notebook processing completes.
- Preserve prior lecture attempts; label corrected notes with the new attempt and source. Never silently overwrite the original evidence.
- The sample code intentionally omits a base case in the first scene. The re-teach button shows a corrected visual example only; it does not mutate scores.

## Motion
One blink every 5–8 seconds while idle; 2px pencil bob while writing; short brow change on wrong answer; single 300ms happy bounce after pass. Disable all under prefers-reduced-motion. Avoid shaking or shaming the student.

## Demo priority
1. Match palette, board and notebook.
2. Add four SVG expressions.
3. Implement linked evidence and missing-source state.
4. Add red pen reveal, then optional texture and motion.

## Copy for Claude
Implement the classroom using this visual handoff. Use DM Sans for UI, Patrick Hand only for short handwritten notes/chalk titles, and IBM Plex Mono for code. Preserve readable text and keyboard focus. Build the desktop board/notebook split and stack under 740px. Reuse the provided SVG assets. Wire expression state to actual recording, processing and grading results. Evidence selection must highlight the question, notebook entry and exact stored transcript sentence together. Missing evidence must say Not covered in your lecture. Do not add invented scores, learned facts, or backend behavior. Keep the recording controls prominent and distinguish recording from transcription.

## Visual revision
Chalkboard headings now request Lighthouse via local font resolution. Supply the exact licensed Lighthouse WOFF2 before release; several fonts share the name. No Lighthouse font binary is bundled. Until available, Patrick Hand is the visible fallback. Code stays in IBM Plex Mono. Notebook notes use Caveat, with small rotations, cross-outs and decorative scribbles. Eraser, chalk and dust are CSS; no image assets required. Decorative draft cross-outs are outside the evidence span and must not be treated as additional taught facts.

## Ready-to-use React code
See react/INTEGRATION.md. Includes a typed React component, scoped stylesheet and Example.tsx visual fixture. All chalk writing is now pure white. Backend callbacks remain owned by your team.

## Current six-scene design
Open six-scenes/index.html for the latest visual direction. It uses Chalkduster with a Cabin Sketch fallback. The earlier single-screen React handoff is retained as reference; see six-scenes/README.md before integration.
