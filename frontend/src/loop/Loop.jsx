import { useEffect, useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { api } from '../lib/api.js'
import { activeTopic, setActiveTopic } from '../lib/auth.js'
import { seedDemo } from '../lib/demoSeed.js'
import { today as readToday } from '../lib/loopState.js'
import Home from './Home.jsx'
import Notes from './Notes.jsx'
import Teach from './Teach.jsx'
import Quiz from './Quiz.jsx'
import Result from './Result.jsx'
import StudentClasses from '../auth/StudentClasses.jsx'
import StudentTopics from '../auth/StudentTopics.jsx'
import './loop.css'

// The daily loop: Home -> Teach -> Quiz (live exam) -> Result -> (Fix it -> Teach once per wrong question -> Quiz) or Home.
// Home -> Notes to upload the course material the questions are written from.
// Home -> My classes (logged in students) to join a class with the teacher's code.
// Home -> Topics (logged in students) to pick a topic a teacher set: its own Reeta, quizzed on the teacher's notes.
// All shared state lives here; screens call back instead of navigating on their own.
// account: the logged in student's user, or null for the anonymous demo session.
// onSignIn (anonymous only) goes back to the login screen.
export default function Loop({ account = null, onLogout, onSignIn }) {
  const [screen, setScreen] = useState('home')
  const [today, setToday] = useState(readToday)
  const [sources, setSources] = useState(null)   // null while loading
  const [error, setError] = useState(null)
  const [fixQueue, setFixQueue] = useState(null) // [{id, prompt, reason}] every question she got wrong, re taught in turn
  const [fixStep, setFixStep] = useState(0)      // index of the question being re taught
  const fix = fixQueue ? { ...fixQueue[fixStep], step: fixStep, total: fixQueue.length } : null
  const [quiz, setQuiz] = useState(null)         // {questions, score, total, passed, streak}
  const [streakBefore, setStreakBefore] = useState(0)
  const [classes, setClasses] = useState(null)   // the student's classes, null while loading or anonymous
  const [topics, setTopics] = useState(null)     // every topic in their classes, with progress
  const topic = topics?.find((t) => t.id === activeTopic()) || null // the one being taught, null = free practice

  async function loadSources() {
    try { setSources((await api.sources()).sources); setError(null) }
    catch { setError('Reeta can’t reach her classroom. Start the backend: uvicorn app.main:app --port 8000') }
  }
  async function loadClasses() {
    if (!account) return
    try { setClasses((await api.me()).classes) } catch { /* Home just shows no class */ }
  }
  async function loadTopics() {
    if (!account) return
    try {
      const list = (await api.myTopics()).topics
      if (activeTopic() && !list.some((t) => t.id === activeTopic())) { setActiveTopic(null); loadSources() } // left the class
      setTopics(list)
    } catch { /* Home shows free practice */ }
  }
  function refresh() { setToday(readToday()); loadSources(); loadClasses(); loadTopics() }
  function pickTopic(t) { setActiveTopic(t?.id); setSources(null); home() }

  // #demo resets the session and the local streak (see lib/demoSeed.js), then shows Home.
  function maybeDemo() {
    if (window.location.hash !== '#demo') return false
    history.replaceState(null, '', window.location.pathname)
    setSources(null); setFixQueue(null); setQuiz(null); setScreen('home')
    seedDemo().catch((e) => console.warn('[loop] demo reset failed:', e.message)).finally(refresh)
    return true
  }
  useEffect(() => {
    if (!maybeDemo()) refresh()
    window.addEventListener('hashchange', maybeDemo)
    return () => window.removeEventListener('hashchange', maybeDemo)
  }, [])

  // items: null for a fresh lesson, or every wrong question to re teach one after another
  function startTeach(items = null) { setFixQueue(items?.length ? items : null); setFixStep(0); setQuiz(null); setScreen('teach') }
  function home() { setFixQueue(null); setScreen('home'); refresh() }
  // After a recording: the next wrong question, or the quiz once all of them are re taught.
  function taught() {
    if (fixQueue && fixStep + 1 < fixQueue.length) { setFixStep(fixStep + 1); return }
    setStreakBefore(readToday().streak); setScreen('quiz')
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="lp-app">
        <div className="lp-phone">
          {error && <div className="lp-banner" role="alert">{error}</div>}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={screen + (fix?.id || '')} className="lp-screen"
              initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}>
              {screen === 'home' && (
                <Home today={today} sources={sources} onTeach={() => startTeach(null)} onNotes={() => setScreen('notes')}
                  account={account} classes={classes} onClasses={() => setScreen('classes')} onSignIn={onSignIn}
                  topic={topic} topics={topics} onTopics={() => setScreen('topics')} />
              )}
              {screen === 'classes' && account && (
                <StudentClasses user={account} onLogout={onLogout} onClose={home} onChange={loadClasses} />
              )}
              {screen === 'topics' && account && (
                <StudentTopics current={topic} onPick={pickTopic} onClose={home} onClasses={() => setScreen('classes')} />
              )}
              {screen === 'notes' && (
                <Notes sources={sources} onChange={loadSources} onClose={home} />
              )}
              {screen === 'teach' && (
                <Teach fix={fix} sources={sources} topic={topic} onClose={home} onTaught={taught} />
              )}
              {screen === 'quiz' && (
                <Quiz onClose={home} onDone={(q) => { setQuiz(q); setScreen('result') }} />
              )}
              {screen === 'result' && quiz && (
                <Result quiz={quiz} streakBefore={streakBefore} onClose={home}
                  onFix={(items) => startTeach(items)} onDone={home} />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </MotionConfig>
  )
}
