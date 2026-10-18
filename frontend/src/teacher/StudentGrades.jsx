import { useEffect, useState } from 'react'
import { api, errorDetail } from '../lib/api.js'
import { Back, Stat, TopicCell } from './Gradebook.jsx'
import { RESULT_LABEL, dateTime, pct, relativeDay } from './format.js'

// One student in one class: totals across topics, then each topic's quizzes question by question (newest
// first), then their ungraded free practice.
export default function StudentGrades({ classId, studentId, onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.studentGrades(classId, studentId).then(setData).catch((e) => setError(errorDetail(e) || 'Could not load this student.'))
  }, [classId, studentId])

  if (error) return <><Back onBack={onBack} label="Gradebook" /><p className="lp-error" role="alert">{error}</p></>
  if (!data) return <><Back onBack={onBack} label="Gradebook" /><p className="lp-muted">Loading…</p></>

  const { student, summary: s, topics, practice } = data
  const first = student.name.split(' ')[0]
  return (
    <>
      <Back onBack={onBack} label={`${data.class.name} gradebook`} />
      <div className="tc-title-row">
        <div>
          <h1 className="tc-h1">{student.name}</h1>
          <p className="lp-lead">{student.email} · last quiz {relativeDay(s.last_active)}</p>
        </div>
      </div>

      <div className="tc-stats">
        <Stat label="Topics passed" value={`${topics.filter((t) => t.progress.status === 'passed').length} / ${topics.length}`} />
        <Stat label="Quizzes" value={s.quizzes} />
        <Stat label="Average" value={pct(s.average_percent)} />
        <Stat label="Day streak" value={s.streak} />
      </div>

      {topics.length === 0 && (
        <div className="lp-card tc-empty"><b>This class has no topics yet.</b></div>
      )}

      {topics.map(({ topic, progress, attempts }) => (
        <section key={topic.id} className="tc-topic-block">
          <div className="tc-topic-block-head">
            <h2>{topic.title}</h2>
            <TopicCell p={progress} />
          </div>
          {attempts.length === 0
            ? <p className="lp-muted">{progress.status === 'practicing' ? `${first} has started teaching Reeta this topic, but no quiz yet.` : `${first} hasn’t started this topic.`}</p>
            : <>
                {attempts.length > 1 && <Trend attempts={attempts} />}
                <Attempts attempts={attempts} />
              </>}
        </section>
      ))}

      {practice.attempts.length > 0 && (
        <section className="tc-topic-block">
          <div className="tc-topic-block-head">
            <h2>Free practice</h2>
            <span className="lp-muted">Not graded · {practice.attempts.length} quiz{practice.attempts.length === 1 ? '' : 'zes'}</span>
          </div>
          <Attempts attempts={practice.attempts} />
        </section>
      )}
    </>
  )
}

function Attempts({ attempts }) {
  return (
    <div className="tc-attempts">
      {[...attempts].reverse().map((a) => (
        <section key={a.attempt_no} className="lp-card tc-attempt">
          <div className="tc-attempt-head">
            <h3>Quiz {a.attempt_no}</h3>
            <span className="lp-muted">{dateTime(a.created_at)}</span>
            <span className={`tc-score tc-score-lg ${a.passed ? 'is-pass' : ''}`}>{a.score}/{a.total} · {a.percent}%</span>
            <span className={`tc-flag ${a.passed ? 'is-pass' : 'is-struggling'}`}>{a.passed ? 'Passed' : 'Not passed'}</span>
          </div>
          <ol className="tc-questions">
            {a.questions.map((q) => (
              <li key={q.question_id} className={`tc-q is-${q.result}`}>
                <span className="tc-q-mark" aria-hidden="true">{q.result === 'correct' ? '✓' : '✗'}</span>
                <div className="tc-q-body">
                  <div className="tc-q-prompt">{q.prompt || q.question_id}</div>
                  {q.feedback && <div className="lp-muted">{q.feedback}</div>}
                </div>
                <span className={`tc-result is-${q.result}`}>{RESULT_LABEL[q.result] || q.result}</span>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  )
}

// Score per quiz as bars, oldest to newest. Green when passed.
function Trend({ attempts }) {
  return (
    <div className="lp-card tc-trend">
      <span className="lp-section-label">Score per quiz</span>
      <div className="tc-bars" role="img" aria-label={`Scores: ${attempts.map((a) => `${a.percent}%`).join(', ')}`}>
        {attempts.map((a) => (
          <div key={a.attempt_no} className="tc-bar-col" title={`Quiz ${a.attempt_no}: ${a.score}/${a.total}`}>
            <span className="tc-bar-val">{a.percent}%</span>
            <div className="tc-bar-track"><div className={`tc-bar ${a.passed ? 'is-pass' : ''}`} style={{ height: `${Math.max(a.percent, 3)}%` }} /></div>
            <span className="tc-bar-label">{a.attempt_no}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
