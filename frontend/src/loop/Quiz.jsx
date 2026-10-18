import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { api } from '../lib/api.js'
import { playClip, stopClip } from '../lib/clip.js'
import { recordQuiz } from '../lib/loopState.js'
import { lines } from '../lib/reetaLines.js'
import Reeta from './Reeta.jsx'
import { TopBar } from './ui.jsx'

const QUESTIONS = 5
const FACE = `${import.meta.env.BASE_URL}teachback/student-`
// Minimum gap before each event is shown, so Reeta visibly types even when the stream arrives at once.
const PACE = { question_start: 450, answer_delta: 28, answer_done: 250, graded: 550 }

// Quiz: the live exam (POST /exam/run). All questions are listed first; Reeta answers them one at a
// time, typing as the stream arrives, then each answer is graded. Wrong answers highlight the exact
// words of the Professor's lecture she relied on, with a replay button when there is a recording.
export default function Quiz({ onClose, onDone }) {
  const reduce = useReducedMotion()
  const [qs, setQs] = useState(null)          // [{id, prompt, text, status, quote, ..., reason, feedback}]
  const [current, setCurrent] = useState(null)
  const [result, setResult] = useState(null)  // the done event
  const [error, setError] = useState(null)
  const [lectures, setLectures] = useState({})
  const ctrl = useRef(null)
  const queue = useRef([])
  const pumping = useRef(false)
  const started = useRef(false)
  const endRef = useRef(null)

  function update(id, patch) { setQs((list) => list?.map((q) => (q.id === id ? { ...q, ...patch(q) } : q))) }

  function apply(name, d) {
    if (name === 'questions') {
      setQs(d.questions.map((q) => ({ ...q, text: '', status: 'waiting' })))
    } else if (name === 'question_start') {
      setCurrent(d.id); update(d.id, () => ({ status: 'answering' }))
    } else if (name === 'answer_delta') {
      update(d.id, (q) => ({ text: q.text + d.text }))
    } else if (name === 'answer_reset') {
      update(d.id, () => ({ text: '' }))
    } else if (name === 'answer_done') {
      update(d.id, () => ({ status: 'answered', text: d.line, supported: d.supported, quote: d.quote, lecture_id: d.lecture_id,
        quote_start_ms: d.quote_start_ms, quote_end_ms: d.quote_end_ms }))
      if (d.lecture_id) loadLecture(d.lecture_id)
    } else if (name === 'graded') {
      // The judge has the final word: not_taught means the quote did not back the answer.
      update(d.id, (q) => ({ status: 'graded', is_correct: d.is_correct, reason: d.reason, feedback: d.feedback,
        quote: d.reason === 'not_taught' ? null : q.quote }))
    } else if (name === 'done') {
      setCurrent(null); setResult(d)
    } else if (name === 'error') {
      setError(d.message || 'Reeta dropped her pencil.')
    }
  }

  async function pump() {
    if (pumping.current) return
    pumping.current = true
    while (queue.current.length) {
      const [name, d] = queue.current.shift()
      if (!reduce && PACE[name]) await new Promise((r) => setTimeout(r, PACE[name]))
      if (ctrl.current?.signal.aborted) break
      apply(name, d)
    }
    pumping.current = false
  }

  async function loadLecture(id) {
    if (lectures[id]) return
    try {
      const { lectures: all } = await api.lectures()
      setLectures(Object.fromEntries(all.map((l) => [l.id, l])))
    } catch { /* the quote text still shows without the transcript */ }
  }

  async function run() {
    ctrl.current?.abort()
    ctrl.current = new AbortController()
    queue.current = []
    setQs(null); setCurrent(null); setResult(null); setError(null)
    try {
      await api.runExam((name, d) => { queue.current.push([name, d]); pump() }, { questions: QUESTIONS, signal: ctrl.current.signal })
    } catch (e) {
      if (e.name !== 'AbortError') setError('Reeta lost her connection to the classroom. Try the quiz again?')
    }
  }
  useEffect(() => {
    if (!started.current) { started.current = true; run() }
    return () => { ctrl.current?.abort(); stopClip() }
  }, [])

  const graded = qs?.filter((q) => q.status === 'graded') || []
  const score = graded.filter((q) => q.is_correct).length
  const finished = result && qs && graded.length === qs.length

  useEffect(() => {
    if (current || finished) endRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'end' })
  }, [current, qs?.find((q) => q.id === current)?.status, finished])
  const active = qs?.find((q) => q.id === current)
  const lastGraded = graded[graded.length - 1]
  const mood = error ? 'confused' : finished ? (result.passed ? 'proud' : 'confused')
    : active ? 'thinking' : lastGraded ? ({ correct: 'proud', wrong: 'confused', not_taught: 'thinking' }[lastGraded.reason]) : 'thinking'
  const say = error ? 'Something went wrong…'
    : finished ? (result.passed ? 'Done! I think… I think I did it?' : 'Done! Some of these felt weird…')
    : !qs ? lines.quizStart
    : active?.status === 'answering' ? lines.answering
    : lastGraded ? lines.graded[lastGraded.reason] : lines.quizStart

  function finish() {
    stopClip()
    const streak = recordQuiz(result)
    onDone({ ...result, questions: qs, streak })
  }

  return (
    <>
      <TopBar onClose={onClose} title="Reeta’s quiz">
        {qs && <div className="lp-chip lp-score" aria-label={`Score so far ${score} of ${qs.length}`}>{score}/{qs.length}</div>}
      </TopBar>

      <div className="lp-body lp-quiz">
        <Reeta mood={mood} size={112} say={say} idle={false} />

        {!qs && !error && <div className="lp-skeleton" aria-hidden="true" />}
        {qs?.map((q, i) => (
          <QuestionCard key={q.id} q={q} n={i + 1} total={qs.length} lecture={lectures[q.lecture_id]} current={q.id === current} />
        ))}
        <div ref={endRef} className="lp-end" />
      </div>

      <div className="lp-actions">
        {error && <><p className="lp-error" role="alert">{error}</p><button className="lp-btn lp-btn-primary lp-btn-xl" onClick={run}>Try again</button></>}
        {!error && finished && <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={finish}>See how I did</button>}
        {!error && !finished && qs && (
          <p className="lp-hint" aria-live="polite">
            {active ? `Answering question ${qs.indexOf(active) + 1} of ${qs.length}…` : 'Checking her answers…'}
          </p>
        )}
      </div>
    </>
  )
}

function QuestionCard({ q, n, total, lecture, current }) {
  const [playing, setPlaying] = useState(false)
  const [noAudio, setNoAudio] = useState(false)
  const done = q.status === 'graded'
  const hasClip = q.lecture_id && q.quote_end_ms > q.quote_start_ms && !noAudio
  const showQuote = q.quote && (q.status === 'answered' || done)

  async function play() {
    if (playing) { stopClip(); setPlaying(false); return }
    setPlaying(true)
    const ok = await playClip(q.lecture_id, q.quote_start_ms, q.quote_end_ms, () => setPlaying(false)).catch(() => false)
    if (!ok) { setPlaying(false); setNoAudio(true) }
  }

  const state = !done ? q.status : q.is_correct ? 'right' : q.reason === 'not_taught' ? 'missing' : 'wrong'
  return (
    <motion.article className={`lp-card lp-q is-${state} ${current ? 'is-current' : ''}`}
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: (n - 1) * 0.08 }}
      aria-label={`Question ${n} of ${total}${done ? (q.is_correct ? ', correct' : ', wrong') : ''}`}>
      <div className="lp-q-head">
        <span className="lp-q-num">Question {n} of {total}</span>
        {done && (
          <motion.span className={`lp-mark ${q.is_correct ? 'is-right' : q.reason === 'not_taught' ? 'is-missing' : 'is-wrong'}`}
            initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 420, damping: 14 }}>
            {q.is_correct ? '✓' : q.reason === 'not_taught' ? '?' : '✗'}
            <span className="lp-sr">{q.is_correct ? ' correct' : q.reason === 'not_taught' ? ' never taught' : ' wrong'}</span>
          </motion.span>
        )}
        {q.status === 'answering' && <span className="lp-typing" aria-label="Reeta is answering"><i /><i /><i /></span>}
      </div>
      <p className="lp-q-prompt">{q.prompt}</p>

      {q.status !== 'waiting' && (
        <div className="lp-say">
          <img src={`${FACE}${!done ? 'thinking' : q.is_correct ? 'proud' : q.reason === 'not_taught' ? 'thinking' : 'confused'}.svg`} alt="" width="36" height="36" />
          <p className="lp-say-bubble">{q.text || '…'}{q.status === 'answering' && <span className="lp-caret" aria-hidden="true" />}</p>
        </div>
      )}

      {showQuote && (
        <motion.div className={`lp-pen ${done && q.is_correct ? 'is-good' : ''}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}>
          <div className="lp-pen-text">
            <span className="lp-pen-label">{done && !q.is_correct ? 'Because you said' : 'You taught me'}</span>
            <Excerpt lecture={lecture} quote={q.quote} start={q.quote_start_ms} end={q.quote_end_ms} />
          </div>
          {hasClip && (
            <button className={`lp-play ${playing ? 'is-playing' : ''}`} onClick={play}
              aria-label={playing ? 'Stop the clip' : 'Replay your sentence'} title="Replay your sentence">
              {playing
                ? <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" /></svg>
                : <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5L8 5.5Z" fill="currentColor" /></svg>}
            </button>
          )}
        </motion.div>
      )}

      {done && q.reason === 'not_taught' && (
        <div className="lp-pen is-missing"><div className="lp-pen-text"><span className="lp-pen-label">{lines.notTaught}</span></div></div>
      )}
      {done && q.feedback && q.reason !== 'not_taught' && <p className="lp-feedback">{q.feedback}</p>}
    </motion.article>
  )
}

// The quote inside a few words of the surrounding lecture, quoted words highlighted.
// Recorded lectures: the words whose time falls in [start, end]. Typed ones: a text match.
const CONTEXT = 8
function Excerpt({ lecture, quote, start, end }) {
  const words = lecture?.words || []
  if (words.length && end > start) {
    const hit = words.map((w) => (w.start_ms + w.end_ms) / 2 >= start && (w.start_ms + w.end_ms) / 2 <= end)
    const first = hit.indexOf(true), last = hit.lastIndexOf(true)
    if (first >= 0) {
      const from = Math.max(0, first - CONTEXT), to = Math.min(words.length, last + 1 + CONTEXT)
      const join = (a, b) => words.slice(a, b).map((w) => w.w).join(' ')
      return (
        <p className="lp-excerpt">
          {from > 0 && '… '}{first > from && `${join(from, first)} `}
          <span className="lp-hl">{join(first, last + 1)}</span>
          {last + 1 < to && ` ${join(last + 1, to)}`}{to < words.length && ' …'}
        </p>
      )
    }
  }
  const text = lecture?.text || ''
  const at = text.toLowerCase().indexOf((quote || '').toLowerCase())
  if (!text || at < 0) return <p className="lp-excerpt"><span className="lp-hl">{quote}</span></p>
  const before = text.slice(0, at).split(' ').slice(-CONTEXT).join(' ')
  const after = text.slice(at + quote.length).split(' ').slice(0, CONTEXT + 1).join(' ')
  return (
    <p className="lp-excerpt">
      {before.length < at && '… '}{before}<span className="lp-hl">{text.slice(at, at + quote.length)}</span>{after}
      {at + quote.length + after.length < text.length && ' …'}
    </p>
  )
}
