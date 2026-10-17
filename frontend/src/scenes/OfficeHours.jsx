import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import AIStudent from '../components/AIStudent.jsx'
import TeachPanel from '../components/TeachPanel.jsx'
import ConceptMap from '../components/ConceptMap.jsx'
import { api } from '../lib/api.js'

export default function OfficeHours({ answerKey, notebook, onConfirmed, retake, go }) {
  const [asks, setAsks] = useState([])
  const [recording, setRecording] = useState(false)
  const load = () => api.officeHours().then((r) => setAsks(r.concepts))
  useEffect(() => { load() }, [])

  const open = asks.filter((a) => a.status !== 'correct')
  const allFixed = asks.length > 0 && !open.length

  return (
    <div className="scene office-hours">
      <div className="seat">
        <AIStudent expression={recording ? 'listening' : allFixed ? 'happy' : 'confused'} raisedHand={!allFixed && !recording}
          say={recording ? null : allFixed ? 'I think I get it now! Can I retake the Exam?' : open[0]?.question || 'Take the Exam first, then come back.'} />
        <div className="desk" />
      </div>
      <div className="oh-main">
        <div className="paper asks">
          <div className="paper-title small">Questions from the AI student</div>
          {asks.map((a) => (
            <motion.div key={a.concept_id} className={`ask ${a.status}`} layout>
              <b>{a.label}</b> <span className="hand">{a.status === 'correct' ? '✓ got it' : a.question}</span>
            </motion.div>
          ))}
          {!asks.length && <div className="hand dim">Nothing yet. Take the Exam first.</div>}
        </div>
        <TeachPanel kind="office_hours" answerKey={answerKey} onRecordingChange={setRecording}
          prompt={open.length ? `Re teach only: ${open.map((a) => a.label).join(', ')}` : null}
          onConfirmed={(nb) => { onConfirmed(nb); load() }} />
        <div className="row">
          <ConceptMap concepts={notebook?.concepts || []} highlight={open.map((a) => a.concept_id)} height={220} />
          <button className="btn big" onClick={async () => { await retake(); go('exam') }}>Retake the Exam →</button>
        </div>
      </div>
    </div>
  )
}
