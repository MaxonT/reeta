import { useEffect, useState } from 'react'
import { api, errorDetail } from '../lib/api.js'
import Gradebook, { Back } from './Gradebook.jsx'
import Topics from './Topics.jsx'

// One class: its join code, then Gradebook or Topics. Both read the gradebook (topic pass counts too).
export default function ClassView({ classId, tab, onTab, onBack, onStudent }) {
  const [book, setBook] = useState(null)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  async function load() {
    try { setBook(await api.gradebook(classId)); setError(null) }
    catch (e) { setError(errorDetail(e) || 'Could not load this class.') }
  }
  useEffect(() => { load() }, [classId])

  async function copyCode() {
    try { await navigator.clipboard.writeText(book.class.join_code); setCopied(true); setTimeout(() => setCopied(false), 1500) }
    catch { /* clipboard blocked: the code is on screen */ }
  }

  if (error) return <><Back onBack={onBack} /><p className="lp-error" role="alert">{error}</p></>
  if (!book) return <><Back onBack={onBack} /><p className="lp-muted">Loading…</p></>

  return (
    <>
      <Back onBack={onBack} />
      <div className="tc-title-row">
        <div>
          <h1 className="tc-h1">{book.class.name}</h1>
          <p className="lp-lead">{book.students.length} {book.students.length === 1 ? 'student' : 'students'} · {book.topics.length} {book.topics.length === 1 ? 'topic' : 'topics'}</p>
        </div>
        <div className="lp-card tc-join">
          <span className="lp-section-label">Join code</span>
          <span className="tc-join-code">{book.class.join_code}</span>
          <button className="lp-link" onClick={copyCode}>{copied ? 'Copied' : 'Copy'}</button>
        </div>
      </div>

      <div className="tc-tabs" role="tablist" aria-label="Class">
        {[['gradebook', 'Gradebook'], ['topics', `Topics (${book.topics.length})`]].map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'is-on' : ''}
            onClick={() => onTab(key)}>{label}</button>
        ))}
      </div>

      {tab === 'gradebook'
        ? <Gradebook book={book} onStudent={onStudent} onTopics={() => onTab('topics')} />
        : <Topics classId={classId} book={book} onChange={load} />}
    </>
  )
}
