import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import AIStudent from '../components/AIStudent.jsx'
import { api } from '../lib/api.js'

export default function ExamRoom({ exam, setExam, go }) {
  const [shown, setShown] = useState(exam?.revealed ? exam.results.length : 0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!exam || shown >= exam.results.length) return
    const t = setTimeout(() => setShown((n) => n + 1), 1100)
    return () => clearTimeout(t)
  }, [exam, shown])

  async function take() {
    setLoading(true)
    try { const e = await api.takeExam(); setShown(0); setExam(e) } finally { setLoading(false) }
  }

  if (!exam) {
    return (
      <div className="scene exam-room center">
        <AIStudent expression="thinking" say="An Exam? I can only use what you taught me…" />
        <button className="btn big" disabled={loading} onClick={take}>{loading ? 'Handing it out…' : 'Hand out the Exam'}</button>
      </div>
    )
  }

  const done = shown >= exam.results.length
  if (done) exam.revealed = true
  const current = exam.results[Math.min(shown, exam.results.length - 1)]
  const expression = !done ? 'thinking' : exam.passed ? 'happy' : 'confused'
  return (
    <div className="scene exam-room">
      <div className="seat">
        <AIStudent expression={expression} say={done ? (exam.passed ? 'I think I aced it!' : 'Some of these… you never told me.') : current.line} />
        <div className="desk" />
        <div className="hand">Attempt {exam.attempt_no}</div>
      </div>
      <div className="exam-paper">
        <div className="paper-title">Exam: Python recursion</div>
        {exam.results.slice(0, shown).map((r, i) => (
          <motion.div key={r.question_id} className="q" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="q-prompt"><b>{i + 1}.</b> <pre>{r.question.prompt}</pre></div>
            <div className="q-options">
              {r.question.options.map((o) => <span key={o} className={`opt ${o === r.answer ? 'chosen' : ''}`}>{o}</span>)}
              {r.answer === null && <span className="opt chosen idk">I don't know</span>}
            </div>
          </motion.div>
        ))}
        {done && (
          <div className="row">
            <button className="btn red" onClick={() => go('grading')}>Grade it with the red pen →</button>
          </div>
        )}
      </div>
    </div>
  )
}
