import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { api } from '../lib/api.js'
import { TopBar } from './ui.jsx'

const MAX_CHARS = 50000

// Course notes: the material Reeta's quiz questions are written from. Upload .txt / .md or paste.
// With no notes the backend uses the default Python recursion notes.
export default function Notes({ sources, onChange, onClose }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

  async function add(payload) {
    setBusy(true); setError(null)
    try {
      await api.postSource(payload)
      setText('')
      await onChange()
    } catch (e) {
      setError(detail(e) || 'Could not add those notes. Try again?')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }
  async function remove(id) {
    setError(null)
    try { await api.deleteSource(id); await onChange() } catch (e) { setError(detail(e) || 'Could not remove that file.') }
  }

  return (
    <>
      <TopBar onClose={onClose} title="Course notes" />
      <div className="lp-body lp-notes-screen">
        <p className="lp-lead">Reeta’s quiz questions are written from these notes. She only answers with what you teach her.</p>

        <div className="lp-card lp-sources">
          <div className="lp-section-label">Used for the quiz</div>
          {sources === null && <p className="lp-muted">Loading…</p>}
          {sources?.length === 0 && <p className="lp-muted">No notes uploaded, using the default Python recursion notes.</p>}
          <AnimatePresence initial={false}>
            {sources?.map((s) => (
              <motion.div key={s.id} className="lp-source" layout
                initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}>
                <div>
                  <div className="lp-source-name">{s.filename}</div>
                  <div className="lp-muted">{s.chars.toLocaleString()} characters</div>
                </div>
                <button className="lp-icon-btn" onClick={() => remove(s.id)} aria-label={`Remove ${s.filename}`}>
                  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        <div className="lp-card lp-add">
          <div className="lp-section-label">Add notes</div>
          <label className={`lp-btn lp-btn-secondary lp-file ${busy ? 'is-busy' : ''}`}>
            <input ref={fileRef} type="file" accept=".txt,.md" disabled={busy}
              onChange={(e) => e.target.files?.[0] && add({ file: e.target.files[0] })} />
            Upload a .txt or .md file
          </label>
          <label className="lp-sr" htmlFor="lp-paste">Paste notes</label>
          <textarea id="lp-paste" rows={5} value={text} disabled={busy} maxLength={MAX_CHARS}
            onChange={(e) => setText(e.target.value)} placeholder="Or paste your notes here…" />
          <div className="lp-add-row">
            <span className="lp-muted">.txt, .md or pasted text · up to 50,000 characters</span>
            <button className="lp-btn lp-btn-primary" disabled={!text.trim() || busy} onClick={() => add({ text })}>
              {busy ? 'Adding…' : 'Add notes'}
            </button>
          </div>
          {error && <p className="lp-error" role="alert">{error}</p>}
        </div>
      </div>
      <div className="lp-actions">
        <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={onClose}>Done</button>
      </div>
    </>
  )
}

// req() throws "POST /sources: 400 {"detail": "..."}"; show the backend's own message.
function detail(e) {
  const m = /\{.*\}$/s.exec(e?.message || '')
  try { return m ? JSON.parse(m[0]).detail : null } catch { return null }
}
