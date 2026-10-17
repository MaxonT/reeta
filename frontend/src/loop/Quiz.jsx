import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { api } from '../lib/api.js'
import { playClip, stopClip } from '../lib/clip.js'
import { lines } from '../lib/reetaLines.js'
import Reeta from './Reeta.jsx'
import { TopBar } from './ui.jsx'

const FACE = `${import.meta.env.BASE_URL}teachback/student-`

// Quiz: Reeta takes up to 3 questions live, one at a time. Wrong answers show the Professor's own
// sentence with a replay button; untaught concepts say so.
export default function Quiz({ lesson, label, onClose, onDone }) {
  const [quiz, setQuiz] = useState(null)
  const [error, setError] = useState(null)
  const [shown, setShown] = useState(0)
  const reduce = useReducedMotion()
  const started = useRef(false)
  const endRef = useRef(null)

  async function take() {
    setError(null)
    try {
      setQuiz(await api.loopQuiz({ lecture_id: lesson?.lectureId, concept_ids: lesson?.conceptIds }))
      setShown(0)
    } catch { setError('Reeta dropped her pencil. Try the quiz again?') }
  }
  useEffect(() => { if (!started.current) { started.current = true; take() } }, [])
  useEffect(() => () => stopClip(), [])

  useEffect(() => {
    if (!quiz || shown >= quiz.results.length) return
    const t = setTimeout(() => setShown((n) => n + 1), reduce ? 400 : shown === 0 ? 900 : 1700)
    return () => clearTimeout(t)
  }, [quiz, shown, reduce])

  useEffect(() => {
    if (shown > 1) endRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'end' })
  }, [shown])

  const total = quiz?.results.length || 0
  const done = quiz && shown >= total
  const score = quiz ? quiz.results.slice(0, shown).filter((r) => r.is_correct).length : 0
  const mood = !quiz ? 'thinking' : !done ? 'thinking' : quiz.passed ? 'proud' : 'confused'
  const say = !quiz ? lines.quizStart : !done ? lines.quizThinking[Math.min(shown, 2)] : quiz.passed ? 'Done! I think… I think I did it?' : 'Done! Some of these felt weird…'

  return (
    <>
      <TopBar onClose={onClose} title="Reeta’s quiz">
        {quiz && <div className="lp-chip lp-score" aria-label={`Score so far ${score} of ${total}`}>{score}/{total}</div>}
      </TopBar>

      <div className="lp-body lp-quiz">
        <Reeta mood={mood} size={112} say={say} idle={false} />

        {!quiz && !error && <div className="lp-skeleton" aria-hidden="true" />}

        {quiz && quiz.results.slice(0, shown).map((r, i) => (
          <QuestionCard key={r.question_id} r={r} n={i + 1} total={total} label={label} />
        ))}
        {quiz && !total && <p className="lp-hint">No questions today. Teach Reeta a bit more first.</p>}
        <div ref={endRef} />
      </div>

      <div className="lp-actions">
        {error && <><p className="lp-error" role="alert">{error}</p><button className="lp-btn lp-btn-primary lp-btn-xl" onClick={take}>Try again</button></>}
        {done && <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={() => { stopClip(); onDone(quiz) }}>See how I did</button>}
        {quiz && !done && <p className="lp-hint" aria-live="polite">Question {Math.min(shown + 1, total)} of {total}…</p>}
      </div>
    </>
  )
}

function QuestionCard({ r, n, total, label }) {
  const [playing, setPlaying] = useState(false)
  const [noAudio, setNoAudio] = useState(false)
  const quote = r.citations?.[0]
  const hasClip = quote && quote.end_ms > quote.start_ms && !noAudio
  const wrongBecause = !r.is_correct && r.reason === 'misconception' && quote
  const notTaught = !r.is_correct && r.reason === 'not_taught'

  async function play() {
    if (playing) { stopClip(); setPlaying(false); return }
    setPlaying(true)
    const ok = await playClip(quote.lecture_id, quote.start_ms, quote.end_ms, () => setPlaying(false)).catch(() => false)
    if (!ok) { setPlaying(false); setNoAudio(true) }
  }

  return (
    <motion.article className={`lp-card lp-q ${r.is_correct ? 'is-right' : 'is-wrong'}`}
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: 'easeOut' }}
      aria-label={`Question ${n} of ${total}, ${r.is_correct ? 'correct' : 'wrong'}`}>
      <div className="lp-q-head">
        <span className="lp-q-num">Question {n} of {total}</span>
        <motion.span className={`lp-mark ${r.is_correct ? 'is-right' : 'is-wrong'}`}
          initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 0 }}
          transition={{ delay: 0.55, type: 'spring', stiffness: 420, damping: 14 }}>
          {r.is_correct ? '✓' : '✗'}<span className="lp-sr">{r.is_correct ? ' correct' : ' wrong'}</span>
        </motion.span>
      </div>
      <pre className={`lp-q-prompt ${r.question?.prompt?.includes('\n') ? 'is-code' : ''}`}>{r.question?.prompt}</pre>

      <div className="lp-answer">
        <span className="lp-answer-label">Reeta answered</span>
        <span className={`lp-answer-chip ${r.answer === null ? 'is-idk' : ''}`}>{r.answer ?? 'I don’t know'}</span>      </div>

      {r.line && (
        <div className="lp-say">
          <img src={`${FACE}${r.is_correct ? 'proud' : notTaught ? 'thinking' : 'confused'}.svg`} alt="" width="36" height="36" />
          <p className="lp-say-bubble">{r.line}</p>
        </div>
      )}

      {wrongBecause && (
        <motion.div className="lp-pen" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.75 }}>
          <div className="lp-pen-text">
            <span className="lp-pen-label">Because you said</span>
            <q>{quote.text.replace(/[.!?]$/, '')}</q>
          </div>
          {(
            <button className={`lp-play ${playing ? 'is-playing' : ''}`} onClick={play} disabled={!hasClip}
              aria-label={playing ? 'Stop the clip' : hasClip ? 'Replay your sentence' : 'No recording to replay'}
              title={hasClip ? 'Replay your sentence' : 'No recording to replay'}>
              {playing
                ? <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" /></svg>
                : <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5L8 5.5Z" fill="currentColor" /></svg>}
            </button>
          )}
          {!hasClip && <span className="lp-pen-note">{noAudio ? 'Couldn’t load the recording' : 'Typed, so no clip to replay'}</span>}
        </motion.div>
      )}

      {notTaught && (
        <motion.div className="lp-pen is-missing" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.75 }}>
          <div className="lp-pen-text">
            <span className="lp-pen-label">{lines.notTaught}</span>
            <span>{(r.missing_concepts || r.concept_ids || []).map(label).join(', ')}</span>
          </div>
        </motion.div>
      )}
    </motion.article>
  )
}
