import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../lib/api.js'
import { useRecorder } from '../lib/useRecorder.js'

// Chalkboard: push to talk -> chalk transcript -> Professor confirms the AI student's notes.
export default function TeachPanel({ kind = 'lecture', answerKey, onConfirmed, onRecordingChange, prompt }) {
  const rec = useRecorder()
  const [phase, setPhase] = useState('idle') // idle | uploading | confirming
  const [result, setResult] = useState(null)
  const [choices, setChoices] = useState({}) // entry id -> {checked, value} ; 's'+sentence id -> value
  const [typed, setTyped] = useState('')
  const [showType, setShowType] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { onRecordingChange?.(rec.recording) }, [rec.recording])

  useEffect(() => {
    const down = (e) => { if (e.code === 'Space' && !e.repeat && phase === 'idle' && !isTyping(e)) { e.preventDefault(); begin() } }
    const up = (e) => { if (e.code === 'Space' && rec.recording) { e.preventDefault(); end() } }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
  })

  async function begin() {
    setError(null)
    try { await rec.start() } catch (e) { setError(`Microphone unavailable: ${e.message}. Type your Lecture instead.`); setShowType(true) }
  }

  async function end() {
    const out = await rec.stop()
    if (!out) return
    await upload({ blob: out.blob, sentences: out.sentences })
  }

  async function upload(payload) {
    setPhase('uploading')
    try {
      const res = await api.postLecture({ kind, ...payload })
      if (!res.sentences.length) throw new Error('No speech detected. Try again, a little closer to the mic.')
      const c = {}
      for (const e of res.proposed_entries) c[e.id] = { checked: true, value: encode(e), original: encode(e) }
      setChoices(c)
      setResult(res)
      setPhase('confirming')
    } catch (e) {
      setError(e.message)
      setPhase('idle')
    }
  }

  async function confirm() {
    const entry_ids = [], edits = [], additions = []
    for (const e of result.proposed_entries) {
      const ch = choices[e.id]
      if (!ch?.checked || !ch.value) continue
      entry_ids.push(e.id)
      if (ch.value !== ch.original) edits.push({ entry_id: e.id, ...decode(ch.value) })
    }
    for (const s of result.sentences) {
      const v = choices['s' + s.id]
      if (v) additions.push({ sentence_id: s.id, ...decode(v) })
    }
    try {
      const nb = await api.confirm(result.lecture.id, { entry_ids, edits, additions })
      setPhase('idle'); setResult(null); setTyped(''); setShowType(false)
      onConfirmed?.(nb)
    } catch (e) { setError(e.message) }
  }

  const options = conceptOptions(answerKey)
  const liveLines = [...rec.live.finals.map((f) => f.text), rec.live.interim].filter(Boolean)

  return (
    <div className="chalkboard">
      <div className="board-title">{kind === 'office_hours' ? 'Office hours' : 'Today’s Lecture: Python recursion'}</div>
      {prompt && <div className="chalk dim">{prompt}</div>}

      {phase !== 'confirming' && (
        <div className="chalk-lines">
          <AnimatePresence>
            {liveLines.map((line, i) => (
              <motion.div key={i} className="chalk" initial={{ opacity: 0, clipPath: 'inset(0 100% 0 0)' }}
                animate={{ opacity: 1, clipPath: 'inset(0 0% 0 0)' }} transition={{ duration: 0.6 }}>{line}</motion.div>
            ))}
          </AnimatePresence>
          {!liveLines.length && phase === 'idle' && !rec.recording && (
            <div className="chalk dim">Hold the button (or Space) and teach. Release when you are done.</div>
          )}
          {rec.recording && !rec.speechSupported && <div className="chalk dim">Recording… (live chalk needs Chrome)</div>}
          {phase === 'uploading' && <div className="chalk dim">The AI student is writing notes…</div>}
        </div>
      )}

      {phase === 'confirming' && result && (
        <div className="confirm">
          <div className="chalk small">Check what the AI student wrote down. Uncheck or fix anything wrong.</div>
          {result.warning && <div className="chalk small warn">{result.warning}</div>}
          {result.sentences.map((s) => {
            const entries = result.proposed_entries.filter((e) => e.sentence_id === s.id)
            return (
              <div key={s.id} className="confirm-row">
                <div className="chalk">{s.text}</div>
                <div className="tags">
                  {entries.map((e) => (
                    <label key={e.id} className={`tag ${statusOf(choices[e.id]?.value)} ${choices[e.id]?.checked ? '' : 'off'}`}>
                      <input type="checkbox" checked={!!choices[e.id]?.checked}
                        onChange={(ev) => setChoices({ ...choices, [e.id]: { ...choices[e.id], checked: ev.target.checked } })} />
                      <select value={choices[e.id]?.value} onChange={(ev) => setChoices({ ...choices, [e.id]: { ...choices[e.id], value: ev.target.value } })}>
                        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </label>
                  ))}
                  {!entries.length && (
                    <label className={`tag ${statusOf(choices['s' + s.id]) || 'none'}`}>
                      <select value={choices['s' + s.id] || ''} onChange={(ev) => setChoices({ ...choices, ['s' + s.id]: ev.target.value })}>
                        <option value="">not about recursion</option>
                        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </label>
                  )}
                </div>
              </div>
            )
          })}
          <div className="row">
            <button className="btn chalk-btn" onClick={confirm}>Write it in the Notebook</button>
            <button className="btn chalk-btn ghost" onClick={() => { setPhase('idle'); setResult(null) }}>Discard</button>
          </div>
        </div>
      )}

      {phase === 'idle' && (
        <div className="controls">
          <button className={`ptt ${rec.recording ? 'on' : ''}`}
            onPointerDown={(e) => { e.preventDefault(); begin() }} onPointerUp={end} onPointerLeave={() => rec.recording && end()}>
            {rec.recording ? 'Listening… release to finish' : 'Hold to teach'}
          </button>
          <button className="btn chalk-btn ghost" onClick={() => setShowType(!showType)}>Type instead</button>
        </div>
      )}
      {phase === 'idle' && showType && (
        <div className="typed">
          <textarea value={typed} onChange={(e) => setTyped(e.target.value)} rows={4}
            placeholder="A recursive function is a function that calls itself. ..." />
          <button className="btn chalk-btn" disabled={!typed.trim()} onClick={() => upload({ text: typed })}>Teach this</button>
        </div>
      )}
      {error && <div className="chalk small warn">{error}</div>}
    </div>
  )
}

function isTyping(e) { return ['TEXTAREA', 'INPUT', 'SELECT'].includes(e.target.tagName) }
function encode(e) { return `${e.concept_id}|${e.status}|${e.misconception_id || ''}` }
function decode(v) { const [concept_id, status, m] = v.split('|'); return { concept_id, status, misconception_id: m || null } }
function statusOf(v) { return v ? v.split('|')[1] : '' }

function conceptOptions(key) {
  const out = []
  for (const c of key?.concepts || []) {
    out.push({ value: `${c.id}|correct|`, label: `✓ ${c.label}` })
    out.push({ value: `${c.id}|misconception|`, label: `✗ ${c.label}: wrong idea` })
    for (const m of c.misconceptions) out.push({ value: `${c.id}|misconception|${m.id}`, label: `✗ ${c.label}: “${m.description}”` })
  }
  return out
}
