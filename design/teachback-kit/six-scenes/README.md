# Six-scene visual preview

Open index.html locally; keep classroom.css and classroom.js beside it. No install or server is needed. This is the current six-scene design; the older single-screen React component in ../react is an earlier handoff and does not implement this navigation.

All six tabs are interactive. The exam reveals ten sample answers one at a time. Red pen selects question, concept and source sentence together. Office hours loads a fixture fix lecture; retaking changes base-case and stack answers, and the report shows B for those concepts. Progress remains untaught (F). All grades and answers are explicit demo fixtures, not backend grading.

Voice recording and playback are deliberately unconnected. The hold button (or Space while it has focus) previews a sample chalk transcription. The replay button remains disabled because no real audio exists. In the production app, retain your existing recording handlers and backend calls. Render only server-returned transcript, concepts, answers, provenance and grades. Do not copy the fixture answer or grade logic into production. No API keys are included.

Chalkduster is now the first-choice chalkboard font. The supplied image is a sample, not a usable font file. This kit resolves an installed Chalkduster through local(); Cabin Sketch is the web fallback. No Chalkduster font binary is bundled. Add your licensed webfont source to @font-face to make the exact font consistent across devices. Python code remains monospace and all chalk is white.

CSS is scoped to #tb-six. Use it as a visual reference when styling the team's six existing React scenes. The prototype has no access to the team's repository and does not change API contracts. Source files are editable HTML/CSS/JavaScript, with character SVGs embedded in the script so the preview is self-contained.
