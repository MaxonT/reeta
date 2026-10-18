import { useEffect, useState } from 'react'
import { api, errorDetail } from '../lib/api.js'

// The teacher's classes, and making a new one (the backend picks the join code).
export default function Classes({ onOpen }) {
  const [classes, setClasses] = useState(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function load() {
    try { setClasses((await api.me()).classes); setError(null) }
    catch (e) { setError(errorDetail(e) || 'Could not load your classes. Is the backend running?') }
  }
  useEffect(() => { load() }, [])

  async function create(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try { await api.createClass(name); setName(''); await load() }
    catch (err) { setError(errorDetail(err) || 'Could not create the class.') }
    finally { setBusy(false) }
  }

  return (
    <>
      <div className="tc-title-row">
        <div>
          <h1 className="tc-h1">Your classes</h1>
          <p className="lp-lead">Share a class’s join code with your students. Their quiz grades show up here.</p>
        </div>
      </div>

      <form className="lp-card tc-new" onSubmit={create}>
        <label className="ac-field tc-new-field">
          <span>New class</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. CS 101, Period 3" maxLength={200} />
        </label>
        <button className="lp-btn lp-btn-primary" disabled={!name.trim() || busy}>{busy ? 'Creating…' : 'Create class'}</button>
      </form>

      {error && <p className="lp-error" role="alert">{error}</p>}
      {classes === null && !error && <p className="lp-muted">Loading…</p>}
      {classes?.length === 0 && (
        <div className="lp-card tc-empty">
          <b>No classes yet.</b>
          <p className="lp-muted">Create one above, then give your students the join code.</p>
        </div>
      )}

      <div className="tc-class-grid">
        {classes?.map((c) => (
          <button key={c.id} className="lp-card tc-class-card" onClick={() => onOpen(c.id)}>
            <span className="tc-class-name">{c.name}</span>
            <span className="tc-class-meta">{c.student_count} {c.student_count === 1 ? 'student' : 'students'}</span>
            <span className="tc-code-chip" aria-label={`Join code ${c.join_code}`}>{c.join_code}</span>
            <span className="tc-open">Open gradebook →</span>
          </button>
        ))}
      </div>
    </>
  )
}
