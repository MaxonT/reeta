import { useEffect, useState } from 'react'
import { api, errorDetail } from '../lib/api.js'
import { TopBar } from '../loop/ui.jsx'
import './account.css'

// A student's classes, and joining one with the code the teacher shares.
export default function StudentClasses({ user, onLogout, onClose, onChange }) {
  const [classes, setClasses] = useState(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [joined, setJoined] = useState(null)

  async function load() {
    try { setClasses((await api.me()).classes) } catch (e) { setError(errorDetail(e) || 'Could not load your classes.') }
  }
  useEffect(() => { load() }, [])

  async function join(e) {
    e.preventDefault()
    setBusy(true); setError(null); setJoined(null)
    try {
      const cls = await api.joinClass(code)
      setJoined(cls.name); setCode('')
      await load(); onChange?.()
    } catch (err) {
      setError(errorDetail(err) || 'Could not join. Check the code?')
    } finally { setBusy(false) }
  }

  return (
    <>
      <TopBar onClose={onClose} title="My classes" />
      <div className="lp-body lp-notes-screen">
        <div className="lp-card ac-who">
          <div>
            <div className="lp-source-name">{user.name}</div>
            <div className="lp-muted">{user.email} · student</div>
          </div>
          <button className="lp-btn lp-btn-secondary ac-small-btn" onClick={onLogout}>Log out</button>
        </div>

        <div className="lp-card lp-sources">
          <div className="lp-section-label">Classes</div>
          {classes === null && !error && <p className="lp-muted">Loading…</p>}
          {classes?.length === 0 && <p className="lp-muted">You’re not in a class yet. Ask your teacher for the join code.</p>}
          {classes?.map((c) => (
            <div key={c.id} className="lp-source">
              <div>
                <div className="lp-source-name">{c.name}</div>
                <div className="lp-muted">Teacher: {c.teacher_name}</div>
              </div>
            </div>
          ))}
        </div>

        <form className="lp-card lp-add" onSubmit={join}>
          <div className="lp-section-label">Join a class</div>
          <label className="ac-field">
            <span>Join code</span>
            <input className="ac-code-input" value={code} maxLength={6} autoCapitalize="characters"
              autoComplete="off" spellCheck={false} placeholder="K7QM4X"
              onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))} />
          </label>
          <p className="lp-muted">Your teacher sees your quiz scores. Never your recordings or what you said.</p>
          <button className="lp-btn lp-btn-primary" disabled={code.length !== 6 || busy}>{busy ? 'Joining…' : 'Join class'}</button>
          {joined && <p className="ac-ok" role="status">You joined {joined}.</p>}
          {error && <p className="lp-error" role="alert">{error}</p>}
        </form>
      </div>
      <div className="lp-actions">
        <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={onClose}>Done</button>
      </div>
    </>
  )
}
