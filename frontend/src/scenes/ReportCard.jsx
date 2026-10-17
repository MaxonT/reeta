import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import AIStudent from '../components/AIStudent.jsx'
import { api } from '../lib/api.js'

export default function ReportCard({ onReset }) {
  const [rep, setRep] = useState(null)
  useEffect(() => { api.report().then(setRep) }, [])
  if (!rep) return <div className="scene center hand">Loading…</div>
  return (
    <div className="scene report">
      <div className="paper report-card">
        <div className="paper-title">Teaching evaluation</div>
        <div className="hand">Lectures given: {rep.lectures} · Exam attempts: {rep.attempts.map((a) => `${a.score}/${a.total}`).join(' → ') || 'none'}</div>
        <table>
          <tbody>
            {rep.concepts.map((c, i) => (
              <motion.tr key={c.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.15 }}>
                <td className="hand">{c.label}</td>
                <td><span className={`grade g${c.grade}`}>{c.grade}</span></td>
                <td className="hand">{c.comment}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
        <div className="row">
          <button className="btn" onClick={onReset}>Teach a new AI student</button>
        </div>
      </div>
      <div className="seat">
        <AIStudent expression={rep.passed ? 'happy' : 'confused'} say={rep.passed ? 'Thank you, Professor! I passed!' : 'I still need some help…'} />
      </div>
    </div>
  )
}
