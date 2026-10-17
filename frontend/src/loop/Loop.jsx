import { useEffect, useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { api } from '../lib/api.js'
import Home from './Home.jsx'
import Teach from './Teach.jsx'
import Quiz from './Quiz.jsx'
import Result from './Result.jsx'
import './loop.css'

// The daily loop: Home -> Teach -> Quiz -> Result -> (Fix it -> Teach) or Home.
// All shared state lives here; screens call back instead of navigating on their own.
export default function Loop({ onClassroom }) {
  const [screen, setScreen] = useState('home')
  const [today, setToday] = useState(null)
  const [answerKey, setAnswerKey] = useState(null)
  const [error, setError] = useState(null)
  const [fix, setFix] = useState(null)         // {concept_id, label} when re teaching
  const [lesson, setLesson] = useState(null)   // {lectureId, conceptIds} of the lecture just taught
  const [quiz, setQuiz] = useState(null)
  const [streakBefore, setStreakBefore] = useState(0)

  async function loadToday() {
    try { setToday(await api.loopToday()); setError(null) }
    catch { setError('Reeta can’t reach her classroom. Start the backend: uvicorn app.main:app --port 8000') }
  }
  useEffect(() => { loadToday(); api.answerKey().then(setAnswerKey).catch(() => {}) }, [])

  const label = (id) => answerKey?.concepts.find((c) => c.id === id)?.label || id

  function startTeach(target = null) {
    setFix(target); setQuiz(null); setScreen('teach')
  }
  function home() { setFix(null); setScreen('home'); loadToday() }

  return (
    <MotionConfig reducedMotion="user">
      <div className="lp-app">
        <div className="lp-phone">
          {error && <div className="lp-banner" role="alert">{error}</div>}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={screen + (fix?.concept_id || '')} className="lp-screen"
              initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}>
              {screen === 'home' && (
                <Home today={today} onTeach={() => startTeach(null)} onClassroom={onClassroom} />
              )}
              {screen === 'teach' && (
                <Teach today={today} fix={fix} label={label} onClose={home}
                  onTaught={(l) => { setLesson(l); setStreakBefore(today?.streak || 0); setScreen('quiz') }} />
              )}
              {screen === 'quiz' && (
                <Quiz lesson={lesson} label={label} onClose={home}
                  onDone={(q) => { setQuiz(q); setScreen('result') }} />
              )}
              {screen === 'result' && quiz && (
                <Result quiz={quiz} streakBefore={streakBefore} label={label} onClose={home}
                  onFix={(target) => startTeach(target)} onDone={home} />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </MotionConfig>
  )
}
