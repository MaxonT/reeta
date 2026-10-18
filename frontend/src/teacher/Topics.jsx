import { useEffect, useRef, useState } from 'react'
import { api, errorDetail } from '../lib/api.js'

const MAX_QUESTIONS = 10

// A class's topics: make one (title, instructions, quiz length), then give it notes. Every quiz on the topic is
// written by the AI from these notes, and each student teaches their own Reeta on it.
export default function Topics({ classId, book, onChange }) {
  const [topics, setTopics] = useState(null)
  const [open, setOpen] = useState(null) // id of the topic being edited
  const [error, setError] = useState(null)

  async function load() {
    try { setTopics((await api.classTopics(classId)).topics); setError(null) }
    catch (e) { setError(errorDetail(e) || 'Could not load the topics.') }
  }
  useEffect(() => { load() }, [classId])
  async function changed() { await Promise.all([load(), onChange()]) }

  const passed = (id) => book.students.filter((r) => r.topics[String(id)]?.status === 'passed').length

  return (
    <div className="tc-topics">
      <NewTopic classId={classId} onCreated={async (t) => { await changed(); setOpen(t.id) }} />
      {error && <p className="lp-error" role="alert">{error}</p>}
      {topics === null && !error && <p className="lp-muted">Loading…</p>}
      {topics?.map((t) => (
        <section key={t.id} className={`lp-card tc-topic ${open === t.id ? 'is-open' : ''}`}>
          <button className="tc-topic-head" aria-expanded={open === t.id} onClick={() => setOpen(open === t.id ? null : t.id)}>
            <span className="tc-topic-title">{t.title}</span>
            <span className={`tc-notes-count ${t.notes_count ? '' : 'is-missing'}`}>
              {t.notes_count ? `${t.notes_count} note${t.notes_count === 1 ? '' : 's'}` : 'No notes yet'}
            </span>
            <span className="lp-muted">{t.questions_per_quiz} questions · {passed(t.id)} / {book.students.length} passed</span>
            <span className="tc-chevron" aria-hidden="true">{open === t.id ? '▴' : '▾'}</span>
          </button>
          {open === t.id && <TopicEditor topic={t} onChange={changed} />}
        </section>
      ))}
    </div>
  )
}

function NewTopic({ classId, onCreated }) {
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  async function create(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try { const t = await api.createTopic(classId, { title }); setTitle(''); await onCreated(t) }
    catch (err) { setError(errorDetail(err) || 'Could not add the topic.') }
    finally { setBusy(false) }
  }
  return (
    <form className="lp-card tc-new" onSubmit={create}>
      <label className="ac-field tc-new-field">
        <span>New topic</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Photosynthesis" maxLength={200} />
      </label>
      <button className="lp-btn lp-btn-primary" disabled={!title.trim() || busy}>{busy ? 'Adding…' : 'Add topic'}</button>
      {error && <p className="lp-error tc-new-error" role="alert">{error}</p>}
    </form>
  )
}

function TopicEditor({ topic, onChange }) {
  const [form, setForm] = useState({ title: topic.title, instructions: topic.instructions, questions_per_quiz: topic.questions_per_quiz })
  const [notes, setNotes] = useState(null)
  const [paste, setPaste] = useState('')
  const [busy, setBusy] = useState(null) // 'save' | 'notes'
  const [msg, setMsg] = useState(null)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)
  const dirty = form.title !== topic.title || form.instructions !== topic.instructions || form.questions_per_quiz !== topic.questions_per_quiz

  async function loadNotes() {
    try { setNotes((await api.topic(topic.id)).notes) } catch (e) { setError(errorDetail(e) || 'Could not load the notes.') }
  }
  useEffect(() => { loadNotes() }, [topic.id])

  async function run(kind, fn, done) {
    setBusy(kind); setError(null); setMsg(null)
    try { await fn(); setMsg(done) } catch (e) { setError(errorDetail(e) || 'Something went wrong. Try again?') }
    finally { setBusy(null) }
  }
  const save = (e) => { e.preventDefault(); run('save', async () => { await api.updateTopic(topic.id, form); await onChange() }, 'Saved.') }
  const addNotes = (payload) => run('notes', async () => {
    await api.addTopicNotes(topic.id, payload); setPaste(''); await loadNotes(); await onChange()
    if (fileRef.current) fileRef.current.value = ''
  }, 'Notes added.')
  const removeNotes = (id) => run('notes', async () => { await api.deleteTopicNotes(topic.id, id); await loadNotes(); await onChange() }, 'Notes removed.')

  return (
    <div className="tc-editor">
      <form className="tc-editor-col" onSubmit={save}>
        <div className="lp-section-label">Topic</div>
        <label className="ac-field">
          <span>Title</span>
          <input value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </label>
        <label className="ac-field">
          <span>Instructions for students</span>
          <textarea className="tc-textarea" rows={3} maxLength={2000} value={form.instructions}
            placeholder="What should they teach Reeta? e.g. Explain the light reactions and where glucose comes from."
            onChange={(e) => setForm({ ...form, instructions: e.target.value })} />
        </label>
        <label className="ac-field tc-narrow">
          <span>Questions per quiz</span>
          <select className="tc-select" value={form.questions_per_quiz}
            onChange={(e) => setForm({ ...form, questions_per_quiz: Number(e.target.value) })}>
            {Array.from({ length: MAX_QUESTIONS }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button className="lp-btn lp-btn-primary" disabled={!dirty || !form.title.trim() || busy}>{busy === 'save' ? 'Saving…' : 'Save changes'}</button>
      </form>

      <div className="tc-editor-col">
        <div className="lp-section-label">Notes the quiz is written from</div>
        {notes === null && <p className="lp-muted">Loading…</p>}
        {notes?.length === 0 && <p className="tc-warn">No notes yet. Students can teach Reeta, but she can’t take a quiz until you add some.</p>}
        {notes?.map((n) => (
          <div key={n.id} className="lp-source">
            <div>
              <div className="lp-source-name">{n.filename}</div>
              <div className="lp-muted">{n.chars.toLocaleString()} characters</div>
            </div>
            <button className="lp-icon-btn" onClick={() => removeNotes(n.id)} disabled={!!busy} aria-label={`Remove ${n.filename}`}>
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>
            </button>
          </div>
        ))}
        <label className={`lp-btn lp-btn-secondary lp-file ${busy === 'notes' ? 'is-busy' : ''}`}>
          <input ref={fileRef} type="file" accept=".txt,.md,.pdf,.docx" disabled={!!busy}
            onChange={(e) => e.target.files?.[0] && addNotes({ file: e.target.files[0] })} />
          Upload a PDF, Word, .txt or .md file
        </label>
        <label className="lp-sr" htmlFor={`paste-${topic.id}`}>Paste notes</label>
        <textarea id={`paste-${topic.id}`} className="tc-textarea" rows={4} value={paste} disabled={!!busy} maxLength={50000}
          onChange={(e) => setPaste(e.target.value)} placeholder="Or paste notes here…" />
        <button className="lp-btn lp-btn-secondary" disabled={!paste.trim() || !!busy} onClick={() => addNotes({ text: paste })}>
          {busy === 'notes' ? 'Adding…' : 'Add pasted notes'}
        </button>
      </div>

      {(msg || error) && (
        <div className="tc-editor-msg">
          {msg && <p className="ac-ok" role="status">{msg}</p>}
          {error && <p className="lp-error" role="alert">{error}</p>}
        </div>
      )}
    </div>
  )
}
