import { useEffect, useState } from 'react'
import { api, errorDetail } from '../lib/api.js'
import { TopBar } from '../loop/ui.jsx'
import './account.css'

export const STATUS_LABEL = { not_started: 'Not started', practicing: 'Practicing', passed: 'Passed' }

// Pick what to teach Reeta: a topic a teacher set (each has its own Reeta), or free practice.
export default function StudentTopics({ current, onPick, onClose, onClasses }) {
  const [topics, setTopics] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.myTopics().then((d) => setTopics(d.topics)).catch((e) => setError(errorDetail(e) || 'Could not load your topics.'))
  }, [])

  const byClass = {}
  for (const t of topics || []) (byClass[t.class_name] ||= []).push(t)

  return (
    <>
      <TopBar onClose={onClose} title="What are we learning?" />
      <div className="lp-body lp-notes-screen">
        {error && <p className="lp-error" role="alert">{error}</p>}
        {topics === null && !error && <p className="lp-muted">Loading…</p>}
        {topics?.length === 0 && (
          <div className="lp-card ac-empty">
            <b>No topics yet.</b>
            <p className="lp-muted">When your teacher adds a topic to your class, it shows up here.</p>
            <button className="lp-link" onClick={onClasses}>Join a class</button>
          </div>
        )}

        {Object.entries(byClass).map(([className, list]) => (
          <div key={className} className="ac-topic-group">
            <div className="lp-section-label">{className}</div>
            {list.map((t) => (
              <button key={t.id} className={`lp-card ac-topic ${current?.id === t.id ? 'is-on' : ''}`}
                aria-pressed={current?.id === t.id} onClick={() => onPick(t)}>
                <span className="ac-topic-head">
                  <b>{t.title}</b>
                  <span className={`ac-status is-${t.progress.status}`}>{STATUS_LABEL[t.progress.status]}</span>
                </span>
                {t.instructions && <span className="ac-topic-text">{t.instructions}</span>}
                <span className="lp-muted">
                  {t.progress.quizzes ? `${t.progress.quizzes} quiz${t.progress.quizzes === 1 ? '' : 'zes'} · best ${t.progress.best_percent}%` : `${t.questions_per_quiz} questions a quiz`}
                </span>
              </button>
            ))}
          </div>
        ))}

        <div className="ac-topic-group">
          <div className="lp-section-label">On your own</div>
          <button className={`lp-card ac-topic ${!current ? 'is-on' : ''}`} aria-pressed={!current} onClick={() => onPick(null)}>
            <span className="ac-topic-head"><b>Free practice</b></span>
            <span className="ac-topic-text">Teach Reeta anything from your own notes. Not graded by your teacher.</span>
          </button>
        </div>
      </div>
    </>
  )
}
