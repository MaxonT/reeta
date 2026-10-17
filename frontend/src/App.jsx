import { useEffect, useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { api } from './lib/api.js'
import LectureHall from './scenes/LectureHall.jsx'
import NotebookScene from './scenes/NotebookScene.jsx'
import ExamRoom from './scenes/ExamRoom.jsx'
import Grading from './scenes/Grading.jsx'
import OfficeHours from './scenes/OfficeHours.jsx'
import ReportCard from './scenes/ReportCard.jsx'

const SCENES = [
  ['lecture', 'Lecture hall'],
  ['notebook', 'Notebook'],
  ['exam', 'Exam room'],
  ['grading', 'Red pen'],
  ['office', 'Office hours'],
  ['report', 'Report card'],
]

export default function App() {
  const [scene, setScene] = useState('lecture')
  const [answerKey, setAnswerKey] = useState(null)
  const [notebook, setNotebook] = useState(null)
  const [lectures, setLectures] = useState([])
  const [exam, setExam] = useState(null)
  const [error, setError] = useState(null)

  async function refresh() {
    try {
      const [nb, lec] = await Promise.all([api.notebook(), api.lectures()])
      setNotebook(nb); setLectures(lec.lectures); setError(null)
    } catch (e) { setError('Backend not reachable. Start it with: uvicorn app.main:app --port 8000') }
  }
  useEffect(() => { api.answerKey().then(setAnswerKey).catch(() => {}); refresh() }, [])

  function onConfirmed(nb) { setNotebook(nb); setExam(null); refresh() }
  async function retake() { const e = await api.takeExam(); setExam(e) }
  async function reset() { await api.reset(); setExam(null); await refresh(); setScene('lecture') }

  const props = { answerKey, notebook, lectures, exam, setExam, onConfirmed, retake, go: setScene, onReset: reset }
  return (
    <MotionConfig reducedMotion="user">
    <div className="app">
      <header>
        <div className="logo">Reeta <span>teach the AI student</span></div>
        <nav>
          {SCENES.map(([id, name], i) => (
            <button key={id} className={scene === id ? 'active' : ''} onClick={() => setScene(id)}>{i + 1}. {name}</button>
          ))}
        </nav>
        <button className="reset" onClick={reset} title="Start over">↺</button>
      </header>
      {error && <div className="banner">{error}</div>}
      <AnimatePresence mode="wait">
        <motion.main key={scene} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.25 }}>
          {scene === 'lecture' && <LectureHall {...props} />}
          {scene === 'notebook' && <NotebookScene {...props} />}
          {scene === 'exam' && <ExamRoom {...props} />}
          {scene === 'grading' && <Grading {...props} />}
          {scene === 'office' && <OfficeHours {...props} />}
          {scene === 'report' && <ReportCard {...props} />}
        </motion.main>
      </AnimatePresence>
    </div>
    </MotionConfig>
  )
}
