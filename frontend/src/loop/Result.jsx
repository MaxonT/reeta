import { useMemo } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import Reeta from './Reeta.jsx'
import { Flame, TopBar } from './ui.jsx'

const COLORS = ['#12805C', '#E8B85A', '#FF8A3D', '#5B8DEF', '#E5484D']

// Result: a big reaction. Pass: proud, confetti, streak +1. Fail: confused, and a Fix it button that
// re teaches the first concept she got wrong.
export default function Result({ quiz, streakBefore = 0, label, onClose, onFix, onDone }) {
  const reduce = useReducedMotion()
  const passed = quiz.passed
  const streak = quiz.streak ?? streakBefore
  const bumped = passed && streak > streakBefore
  const target = fixTarget(quiz.results)
  const wrong = quiz.results.filter((r) => !r.is_correct)

  return (
    <>
      <TopBar onClose={onClose} />
      <div className="lp-body lp-result">
        {passed && !reduce && <Confetti />}
        <motion.div className={`lp-score-big ${passed ? 'is-pass' : 'is-fail'}`}
          initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 15 }}>
          {quiz.score}<span>/{quiz.total}</span>
        </motion.div>
        <Reeta mood={passed ? 'proud' : 'confused'} size={200} say={quiz.result_line} idle={false} />

        {passed ? (
          <motion.div className="lp-card lp-streak-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
            <motion.div className="lp-streak-icon" initial={reduce ? false : { scale: 0.4, rotate: -12 }} animate={{ scale: 1, rotate: 0 }}
              transition={{ delay: 0.5, type: 'spring', stiffness: 300, damping: 10 }}>
              <Flame size={40} />
            </motion.div>
            <div>
              <div className="lp-streak-num">
                {streak} day streak
                {bumped && <motion.span className="lp-plus" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 }}>+1</motion.span>}
              </div>
              <div className="lp-streak-sub">{bumped ? 'Reeta passed today. Come back tomorrow to keep it going.' : 'Today already counts. See you tomorrow!'}</div>
            </div>
          </motion.div>
        ) : (
          <motion.div className="lp-card lp-missed" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
            <div className="lp-section-label">What she got wrong</div>
            <ul>
              {wrong.map((r) => (
                <li key={r.question_id}>
                  <b>{(r.reason === 'not_taught' ? r.missing_concepts : r.concept_ids).map(label).join(', ')}</b>
                  <span>{r.reason === 'not_taught' ? 'never taught' : 'taught a wrong idea'}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </div>

      <div className="lp-actions">
        {!passed && target && (
          <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={() => onFix({ concept_id: target, label: label(target) })}>
            Fix it: {label(target)}
          </button>
        )}
        <button className={`lp-btn lp-btn-xl ${passed ? 'lp-btn-primary' : 'lp-btn-secondary'}`} onClick={onDone}>Done for today</button>
      </div>
    </>
  )
}

function fixTarget(results) {
  const mis = results.find((r) => !r.is_correct && r.reason === 'misconception')
  if (mis) return mis.concept_ids?.[0]
  const missing = results.find((r) => !r.is_correct)
  return missing ? (missing.missing_concepts?.[0] || missing.concept_ids?.[0]) : null
}

function Confetti() {
  const bits = useMemo(() => Array.from({ length: 22 }, (_, i) => ({
    x: (Math.random() - 0.5) * 340, r: Math.random() * 540 - 270, d: 0.9 + Math.random() * 0.9,
    delay: Math.random() * 0.25, c: COLORS[i % COLORS.length], w: 6 + Math.random() * 6, round: i % 3 === 0, peak: -120 - Math.random() * 80,
  })), [])
  return (
    <div className="lp-confetti" aria-hidden="true">
      {bits.map((b, i) => (
        <motion.span key={i} style={{ background: b.c, width: b.w, height: b.round ? b.w : b.w * 1.6, borderRadius: b.round ? '50%' : 2 }}
          initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
          animate={{ x: b.x, y: [0, b.peak, 260], opacity: [1, 1, 0], rotate: b.r }}
          transition={{ duration: b.d + 0.8, delay: b.delay, ease: 'easeOut' }} />
      ))}
    </div>
  )
}
