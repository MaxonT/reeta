import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { api } from '../lib/api.js'
import { useRecorder } from '../lib/useRecorder.js'
import { lines } from '../lib/reetaLines.js'
import Reeta from './Reeta.jsx'
import { TopBar } from './ui.jsx'

const LIMIT_MS = 60000
const RING_R = 64
const RING_C = 2 * Math.PI * RING_R

// Teach: hold to talk (or Space), or type. Same recorder and transcript flow as TeachPanel, but every
// proposed note is confirmed automatically: Reeta believes everything you say.
export default function Teach({ today, fix, label, onClose, onTaught }) {
  const rec = useRecorder()
  const [phase, setPhase] = useState('idle') // idle | processing | notes
  const [elapsed, setElapsed] = useState(0)
  const [showType, setShowType] = useState(false)
  const [typed, setTyped] = useState('')
  const [error, setError] = useState(null)
  const [notes, setNotes] = useState([])
  const [shown, setShown] = useState(0)
  const [lesson, setLesson] = useState(null)
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

  // Notes appear one by one.
  useEffect(() => {
    if (phase !== 'notes' || shown >= notes.length) return
    const t = setTimeout(() => setShown((n) => n + 1), shown === 0 ? 350 : 650)
    return () => clearTimeout(t)
  }, [phase, shown, notes.length])

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
      if (!res.sentences.length) throw new Error('I didn’t catch any words. Try again a little closer to the mic?')
      const entries = res.proposed_entries
      if (entries.length) await api.confirm(res.lecture.id, { entry_ids: entries.map((e) => e.id) })
      const order = new Map(res.sentences.map((s, i) => [s.id, i]))
      setNotes([...entries].sort((a, b) => order.get(a.sentence_id) - order.get(b.sentence_id) || a.id - b.id))
      setLesson({ lectureId: res.lecture.id, conceptIds: [...new Set(entries.map((e) => e.concept_id))], hasAudio: res.lecture.has_audio })
      setShown(0)
      setPhase('notes')
    } catch (e) {
      setError(e.message.startsWith('POST') ? 'Something went wrong saving my notes. Try once more?' : e.message)
      setPhase('idle')
    }
  }

  function again() { setPhase('idle'); setNotes([]); setLesson(null); setTyped('') }

  const live = [...rec.live.finals.map((f) => f.text), rec.live.interim].filter(Boolean).join(' ')
  const noNotes = phase === 'notes' && !notes.length
  const mood = rec.recording ? 'listening' : phase === 'processing' ? 'thinking' : noNotes ? 'confused' : 'listening'
  const say = rec.recording ? lines.recording
    : phase === 'processing' ? lines.processing
    : noNotes ? lines.notesEmpty
    : phase === 'notes' ? lines.notesDone
    : fix ? lines.teachFix(fix.label, fix.concept_id) : lines.teachIdle
  const allShown = shown >= notes.length
  const secsLeft = Math.max(0, Math.ceil((LIMIT_MS - elapsed) / 1000))

  return (
    <>
      <TopBar onClose={onClose} title={fix ? 'Fix it' : 'Teach Reeta'} />

      <div className="lp-body lp-teach">
        {fix
          ? <div className="lp-context is-fix">Re teach just <b>{fix.label}</b>. Then she retakes the quiz.</div>
          : today?.ask && <div className="lp-context">Reeta asked about <b>{today.ask.label}</b>. Any recursion counts.</div>}

        <Reeta mood={mood} size={phase === 'notes' ? 132 : 176} say={say} idle={phase === 'idle'} pulse={rec.recording} />

        {phase !== 'notes' && (live || phase === 'processing') && (
          <div className="lp-live" aria-live="polite">
            <span className="lp-live-label">{rec.recording ? 'Listening' : 'You said'}</span>
            <p>{live || typed || '…'}</p>
          </div>
        )}

        {phase === 'notes' && (
          <div className="lp-notes">
            <div className="lp-section-label">Reeta’s notes</div>
            <AnimatePresence>
              {notes.slice(0, shown).map((n) => (
                <motion.div key={n.id} className={`lp-note ${n.status === 'misconception' ? 'is-off' : ''}`}
                  initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.28 }}>
                  <div className="lp-note-label">
                    <span className="lp-note-dot" aria-hidden="true" />
                    {label(n.concept_id)}
                    {n.status === 'misconception' && <span className="lp-sr"> (Reeta may have this one wrong)</span>}
                  </div>
                  <p className="lp-note-quote">“{n.sentence?.text}”</p>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      <div className="lp-actions">
        {error && <p className="lp-error" role="alert">{error}</p>}

        {phase === 'notes' ? (
          noNotes
            ? <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={again}>Try again</button>
            : <motion.button className="lp-btn lp-btn-primary lp-btn-xl" onClick={() => onTaught(lesson)} disabled={!allShown}
                initial={{ opacity: 0.6 }} animate={{ opacity: allShown ? 1 : 0.6 }}>Quiz Reeta</motion.button>
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
                  placeholder={fix ? `Explain ${fix.label.toLowerCase()} again, in your own words…` : 'A recursive function is a function that calls itself…'} />
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
