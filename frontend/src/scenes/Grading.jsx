import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import ConceptMap from '../components/ConceptMap.jsx'
import AIStudent from '../components/AIStudent.jsx'
import { playClip, stopClip } from '../lib/clip.js'

// Red pen: clicking a wrong answer lights up the question, the Notebook node and the
// Professor's exact sentence together, and replays that audio clip.
export default function Grading({ exam, notebook, lectures, answerKey, go }) {
  const [sel, setSel] = useState(null)
  const [playing, setPlaying] = useState(null)
  const refs = useRef({})
  const label = (id) => answerKey?.concepts.find((c) => c.id === id)?.label || id

  const selected = exam?.results.find((r) => r.question_id === sel)
  const hlConcepts = selected ? selected.concept_ids : []
  const hlSentences = new Set(selected ? selected.sentence_ids : [])

  useEffect(() => {
    const first = selected?.sentence_ids[0]
    if (first && refs.current[first]) refs.current[first].scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [sel])
  useEffect(() => () => stopClip(), [])

  if (!exam) return <div className="scene center"><div className="hand">No Exam to grade yet.</div><button className="btn" onClick={() => go('exam')}>Go to the Exam room</button></div>

  async function select(r) {
    setSel(r.question_id)
    const c = r.citations[0]
    if (!r.is_correct && c) play(c)
    else stopClip()
  }
  async function play(s) {
    setPlaying(s.sentence_id ?? s.id)
    const ok = await playClip(s.lecture_id, s.start_ms, s.end_ms, () => setPlaying(null)).catch(() => false)
    if (!ok) setPlaying(null)
  }

  return (
    <div className="scene grading">
      <div className="scene-head">
        <div className="tiny">04 / Red pen</div>
        <h1>Follow the mistake back to the lesson.</h1>
        <p>Question, concept, your exact words. Select a red mark to trace it.</p>
      </div>
      <div className="exam-paper graded">
        <div className="paper-title">Exam, attempt {exam.attempt_no}
          <motion.span className="score" initial={{ scale: 2, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>{exam.score}/{exam.total}</motion.span>
        </div>
        {exam.results.map((r, i) => (
          <div key={r.question_id} className={`q clickable ${sel === r.question_id ? 'hl' : ''}`} onClick={() => select(r)}>
            <span className={`pen ${r.is_correct ? 'ok' : 'bad'}`}>{r.is_correct ? '✓' : '✗'}</span>
            <div className="q-prompt"><b>{i + 1}.</b> <pre>{r.question.prompt}</pre></div>
            <div className="answer hand">AI student: {r.answer ?? 'I don’t know'}</div>
            {sel === r.question_id && (
              <motion.div className="red-note" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                {r.reason === 'misconception' && <>You taught a wrong idea about <b>{r.concept_ids.map(label).join(', ')}</b>.</>}
                {r.reason === 'not_taught' && <>You never taught <b>{r.missing_concepts.map(label).join(', ')}</b>.</>}
                {r.reason === 'not_taught' && !r.sentence_ids.length && <div className="missing-src">Not covered in your lecture.</div>}
                {r.reason === 'correct' && <>Correct, using what you taught about {r.concept_ids.map(label).join(', ')}.</>}
                <div className="hand">“{r.line}”</div>
              </motion.div>
            )}
          </div>
        ))}
        <div className="row">
          {!exam.passed && <button className="btn" onClick={() => go('office')}>Go to Office hours →</button>}
          {exam.passed && <button className="btn" onClick={() => go('report')}>See the Report card →</button>}
        </div>
      </div>

      <div className="side">
        <div className="grading-student">
          <AIStudent expression={selected && !selected.is_correct ? 'confused' : 'listening'} size={96} />
        </div>
        <div className="tiny">Linked concept</div>
        <ConceptMap concepts={notebook?.concepts || []} highlight={hlConcepts} height={320} />
        <div className="transcript">
          <div className="paper-title small">What you said</div>
          {(lectures || []).map((lec) => (
            <div key={lec.id} className="lec">
              <div className="lec-head">{lec.kind === 'office_hours' ? 'Office hours' : 'Lecture'} #{lec.id}</div>
              {lec.sentences.map((s) => (
                <div key={s.id} ref={(el) => (refs.current[s.id] = el)}
                  className={`sent ${hlSentences.has(s.id) ? 'hl' : ''} ${playing === s.id ? 'playing' : ''}`}
                  onClick={() => lec.has_audio && play({ ...s, lecture_id: lec.id, sentence_id: s.id })}>
                  {lec.has_audio && s.end_ms > s.start_ms && <span className="play">▶</span>} {s.text}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
