import { motion } from 'framer-motion'
import ConceptMap from '../components/ConceptMap.jsx'
import AIStudent, { moodFromNotebook } from '../components/AIStudent.jsx'
import { countStatus } from './LectureHall.jsx'

export default function NotebookScene({ notebook, answerKey, go }) {
  const concepts = notebook?.concepts || []
  const entries = notebook?.entries || []
  const label = (id) => answerKey?.concepts.find((c) => c.id === id)?.label || id
  const c = countStatus(concepts)
  return (
    <div className="scene notebook-scene">
      <div className="paper">
        <div className="paper-title">My Notebook</div>
        {!entries.length && <div className="hand dim">Empty. My Professor has not taught me anything yet.</div>}
        {entries.map((e, i) => (
          <motion.div key={e.id} className={`note ${e.status} ${e.superseded_by ? 'superseded' : ''}`}
            initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
            <span className="note-tag">{label(e.concept_id)}</span>
            <span className="hand">“{e.sentence.text}”</span>
          </motion.div>
        ))}
      </div>
      <div className="side">
        <ConceptMap concepts={concepts} />
        <div className="legend hand">
          <span className="dot correct" /> {c.correct} learned
          <span className="dot misconception" /> {c.misconception} wrong idea
          <span className="dot missing" /> {c.missing} never taught
        </div>
        <div className="row">
          <AIStudent expression={moodFromNotebook(concepts)} size={110} />
          <button className="btn" onClick={() => go('exam')}>Give the Exam →</button>
        </div>
      </div>
    </div>
  )
}
