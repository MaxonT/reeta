import { useState } from 'react'
import TeachPanel from '../components/TeachPanel.jsx'
import AIStudent, { moodFromNotebook } from '../components/AIStudent.jsx'

export default function LectureHall({ answerKey, notebook, onConfirmed, go }) {
  const [recording, setRecording] = useState(false)
  const [said, setSaid] = useState(null)
  const mood = recording ? 'listening' : said ? moodFromNotebook(notebook?.concepts) : 'listening'
  const entries = notebook?.entries || []
  const label = (id) => answerKey?.concepts.find((c) => c.id === id)?.label || id

  function confirmed(nb) {
    const counts = countStatus(nb.concepts)
    setSaid(counts.correct + counts.misconception
      ? `Got it! I wrote ${counts.correct + counts.misconception} of 5 ideas in my Notebook.`
      : 'Hmm, I did not learn anything about recursion from that.')
    onConfirmed(nb)
  }

  return (
    <div className="scene lecture-hall">
      <div className="scene-head">
        <div className="tiny">01 / Lecture hall</div>
        <h1>The floor is yours, Professor.</h1>
        <p>Teach out loud. Your student starts with a blank page.</p>
      </div>
      <div className="lecture-main">
        <TeachPanel kind="lecture" answerKey={answerKey} onConfirmed={confirmed} onRecordingChange={setRecording} />
        <div className="student-row">
          <AIStudent expression={mood} size={126} say={recording ? null : said || 'I know nothing yet. Teach me recursion!'} />
        </div>
      </div>
      <aside className="paper ruled lecture-notes">
        <div className="tiny">My Notebook</div>
        <div className="paper-title">What I wrote down</div>
        <div className="notes-list">
          {!entries.length && <div className="hand dim">Empty. Teach me something, then check my notes on the board.</div>}
          {entries.map((e) => (
            <div key={e.id} className={`note ${e.status} ${e.superseded_by ? 'superseded' : ''}`}>
              <span className="note-tag">{label(e.concept_id)}</span>
              <span className="hand">“{e.sentence.text}”</span>
            </div>
          ))}
        </div>
        <div className="scribble" aria-hidden="true" />
        <div className="row">
          <button className="btn" onClick={() => go('notebook')}>Peek at my Notebook →</button>
        </div>
      </aside>
    </div>
  )
}

export function countStatus(concepts = []) {
  const c = { correct: 0, misconception: 0, missing: 0 }
  for (const x of concepts) c[x.status]++
  return c
}
