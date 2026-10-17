import { useState } from 'react'
import TeachPanel from '../components/TeachPanel.jsx'
import AIStudent, { moodFromNotebook } from '../components/AIStudent.jsx'

export default function LectureHall({ answerKey, notebook, onConfirmed, go }) {
  const [recording, setRecording] = useState(false)
  const [said, setSaid] = useState(null)
  const mood = recording ? 'listening' : said ? moodFromNotebook(notebook?.concepts) : 'listening'

  function confirmed(nb) {
    const counts = countStatus(nb.concepts)
    setSaid(counts.correct + counts.misconception
      ? `Got it! I wrote ${counts.correct + counts.misconception} of 5 ideas in my Notebook.`
      : 'Hmm, I did not learn anything about recursion from that.')
    onConfirmed(nb)
  }

  return (
    <div className="scene lecture-hall">
      <TeachPanel kind="lecture" answerKey={answerKey} onConfirmed={confirmed} onRecordingChange={setRecording} />
      <div className="seat">
        <AIStudent expression={mood} say={recording ? null : said || 'I know nothing yet. Teach me recursion!'} />
        <div className="desk" />
        <button className="btn" onClick={() => go('notebook')}>Peek at my Notebook →</button>
      </div>
    </div>
  )
}

export function countStatus(concepts = []) {
  const c = { correct: 0, misconception: 0, missing: 0 }
  for (const x of concepts) c[x.status]++
  return c
}
