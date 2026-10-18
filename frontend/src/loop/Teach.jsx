import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../lib/api.js'
import { useRecorder } from '../lib/useRecorder.js'
import { lines } from '../lib/reetaLines.js'
import Reeta from './Reeta.jsx'
import { TopBar } from './ui.jsx'

const LIMIT_MS = 60000
const RING_R = 64
const RING_C = 2 * Math.PI * RING_R

// Teach: hold to talk (or Space), or type. Same recorder as TeachPanel. After the upload Reeta shows
// what she wrote down (the transcript); everything you say goes straight into her notes.
export default function Teach({ fix, sources, onClose, onTaught }) {
  const rec = useRecorder()
  const [phase, setPhase] = useState('idle') // idle | processing | done
  const [elapsed, setElapsed] = useState(0)
  const [showType, setShowType] = useState(false)
  const [typed, setTyped] = useState('')
  const [error, setError] = useState(null)
  const [lecture, setLecture] = useState(null)
  const [warning, setWarning] = useState(null)
  const pressing = useRef(false)
  const t0 = useRef(0)
  const kind = fix ? 'office_hours' : 'lecture'

  // 60 second ring timer; stops the recording at the limit.
  useEffect(() => {
    if (!rec.recording) { setElapsed(0); return }
    t0.current = performance.now()
    const id = setInterval(() => {
      const ms = performance.now() - t0.current
      setElapsed(ms)
      if (ms >= LIMIT_MS) end()
    }, 100)
    return () => clearInterval(id)
  }, [rec.recording])

  // Space to talk, like the classroom.
  useEffect(() => {
    const down = (e) => {
      if (e.code !== 'Space' || e.repeat || isTyping(e) || phase !== 'idle') return
      e.preventDefault(); begin()
    }
    const up = (e) => { if (e.code === 'Space' && pressing.current) { e.preventDefault(); end() } }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
  })

  async function begin() {
    if (pressing.current || phase !== 'idle') return
    pressing.current = true
    setError(null)
    try {
      await rec.start()
      if (!pressing.current) await end(true) // released before the mic was ready
    } catch (e) {
      pressing.current = false
      setError('I can’t hear you, there’s no microphone I can use. Can you type it instead?')
      setShowType(true)
    }
  }

  async function end(force = false) {
    if (!pressing.current && !force) return
    pressing.current = false
    const out = await rec.stop()
    if (!out) return
    await upload({ blob: out.blob, sentences: out.sentences })
  }

  async function upload(payload) {
    setPhase('processing'); setError(null)
    try {
      const res = await api.postLecture({ kind, ...payload })
      if (!res.lecture?.text?.trim()) throw new Error('I didn’t catch any words. Try again a little closer to the mic?')
      setLecture(res.lecture)
      setWarning(res.warning || null)
      setPhase('done')
    } catch (e) {
      setError(e.message.startsWith('POST') ? 'Something went wrong saving my notes. Try once more?' : e.message)
      setPhase('idle')
    }
  }

  function again() { setPhase('idle'); setLecture(null); setWarning(null); setTyped('') }

  const live = [...rec.live.finals.map((f) => f.text), rec.live.interim].filter(Boolean).join(' ')
  const mood = rec.recording ? 'listening' : phase === 'processing' ? 'thinking' : phase === 'done' ? 'proud' : 'listening'
  const say = rec.recording ? lines.recording
    : phase === 'processing' ? lines.processing
    : phase === 'done' ? lines.transcriptDone
    : fix ? lines.teachFix : lines.teachIdle
  const notesName = !sources?.length ? 'Python recursion' : sources.length === 1 ? sources[0].filename : 'your notes'
  const secsLeft = Math.max(0, Math.ceil((LIMIT_MS - elapsed) / 1000))

  return (
    <>
      <TopBar onClose={onClose} title={fix ? 'Fix it' : 'Teach Reeta'} />

      <div className="lp-body lp-teach">
        {fix
          ? <div className="lp-context is-fix"><span className="lp-context-label">Fix this one</span>{fix.prompt}</div>
          : <div className="lp-context">Teach anything from <b>{notesName}</b>. She is quizzed on it next.</div>}

        <Reeta mood={mood} size={phase === 'done' ? 132 : 176} say={say} idle={phase === 'idle'} pulse={rec.recording} />

        {phase !== 'done' && (live || phase === 'processing') && (
          <div className="lp-live" aria-live="polite">
            <span className="lp-live-label">{rec.recording ? 'Listening' : 'You said'}</span>
            <p>{live || typed || '…'}</p>
          </div>
        )}

        {phase === 'done' && lecture && (
          <motion.div className="lp-card lp-transcript" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28 }}>
            <div className="lp-section-label">Reeta’s notes{lecture.has_audio ? ' · recorded' : ' · typed'}</div>
            <p>{lecture.text}</p>
            {warning && <p className="lp-muted">{warning}</p>}
          </motion.div>
        )}
      </div>

      <div className="lp-actions">
        {error && <p className="lp-error" role="alert">{error}</p>}

        {phase === 'done' ? (
          <>
            <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={() => onTaught(lecture)}>Quiz Reeta</button>
            <button className="lp-link" onClick={again}>Teach more first</button>
          </>
        ) : (
          <>
            {!showType && (
              <div className="lp-talk">
                <div className={`lp-ring ${rec.recording ? 'is-on' : ''}`}>
                  <svg viewBox="0 0 148 148" aria-hidden="true">
                    <circle cx="74" cy="74" r={RING_R} className="lp-ring-track" />
                    <circle cx="74" cy="74" r={RING_R} className="lp-ring-fill"
                      strokeDasharray={RING_C} strokeDashoffset={RING_C * (1 - Math.min(1, elapsed / LIMIT_MS))} />
                  </svg>
                  <button className="lp-mic" disabled={phase === 'processing'}
                    aria-label={rec.recording ? 'Recording. Release to finish' : 'Hold to talk'}
                    onPointerDown={(e) => { e.preventDefault(); begin() }}
                    onPointerUp={() => end()} onPointerLeave={() => end()} onPointerCancel={() => end()}
                    onContextMenu={(e) => e.preventDefault()}>
                    {phase === 'processing'
                      ? <span className="lp-spinner" aria-hidden="true" />
                      : <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" /></svg>}
                  </button>
                </div>
                <p className="lp-talk-label">
                  {phase === 'processing' ? 'Reeta is taking notes…'
                    : rec.recording ? <>Release to finish · <b>{secsLeft}s</b></>
                    : <>Hold to talk <span className="lp-kbd">or hold Space</span></>}
                </p>
              </div>
            )}

            {showType && (
              <div className="lp-type">
                <label className="lp-sr" htmlFor="lp-typed">Type your lesson</label>
                <textarea id="lp-typed" rows={4} value={typed} disabled={phase === 'processing'} autoFocus
                  onChange={(e) => setTyped(e.target.value)}
                  onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && typed.trim()) upload({ text: typed }) }}
                  placeholder={fix ? 'Explain it again, in your own words…' : 'A recursive function is a function that calls itself…'} />
                <button className="lp-btn lp-btn-primary lp-btn-xl" disabled={!typed.trim() || phase === 'processing'}
                  onClick={() => upload({ text: typed })}>{phase === 'processing' ? 'Reeta is taking notes…' : 'Teach this'}</button>
              </div>
            )}

            <button className="lp-link" disabled={rec.recording || phase === 'processing'}
              onClick={() => { setShowType(!showType); setError(null) }}>
              {showType ? 'Talk instead' : 'Type instead'}
            </button>
          </>
        )}
      </div>
    </>
  )
}

// Space keeps its normal meaning in fields and on other buttons; elsewhere it is push to talk.
function isTyping(e) {
  const t = e.target
  return ['TEXTAREA', 'INPUT', 'SELECT'].includes(t.tagName) || (t.tagName === 'BUTTON' && !t.classList.contains('lp-mic'))
}
