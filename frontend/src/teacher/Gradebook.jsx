import { useMemo, useState } from 'react'
import { attention, daysAgo, pct, relativeDay } from './format.js'

export const STATUS_LABEL = { not_started: 'Not started', practicing: 'Practicing', passed: 'Passed' }
const STATUS_RANK = { not_started: 0, practicing: 1, passed: 2 }

// The class gradebook: a row per student, a column per topic (status and best score), then totals across topics.
export default function Gradebook({ book, onStudent, onTopics }) {
  const [sort, setSort] = useState({ key: 'name', dir: 1 })

  // key, label, value for sorting, numeric
  const columns = useMemo(() => [
    ['name', 'Student', (r) => r.student.name.toLowerCase(), false],
    ...book.topics.map((t) => [`t${t.id}`, t.title, (r) => {
      const p = r.topics[String(t.id)]
      return STATUS_RANK[p.status] * 1000 + (p.best_percent ?? -1)
    }, true, t.id]),
    ['average', 'Average', (r) => r.summary.average_percent ?? -1, true],
    ['active', 'Last quiz', (r) => -(daysAgo(r.summary.last_active) ?? 1e9), false],
    ['wrong', 'Taught wrong', (r) => r.summary.wrong, true],
    ['not_taught', 'Never taught', (r) => r.summary.not_taught, true],
    ['practice', 'Free practice', (r) => r.practice.quizzes, true],
  ], [book])

  const rows = useMemo(() => {
    const col = columns.find(([k]) => k === sort.key) || columns[0]
    return [...book.students].sort((a, b) => {
      const x = col[2](a), y = col[2](b)
      return (x < y ? -1 : x > y ? 1 : 0) * sort.dir || a.student.name.localeCompare(b.student.name)
    })
  }, [book, sort, columns])

  const totals = useMemo(() => {
    const s = book.students.map((r) => r.summary)
    const taking = s.filter((x) => x.quizzes)
    const cells = book.students.flatMap((r) => Object.values(r.topics))
    return {
      average: taking.length ? Math.round(taking.reduce((n, x) => n + x.average_percent, 0) / taking.length) : null,
      passed: cells.filter((c) => c.status === 'passed').length,
      cells: cells.length,
      activeWeek: s.filter((x) => x.quizzes && daysAgo(x.last_active) < 7).length,
      attention: book.students.filter((r) => attention(r)).length,
    }
  }, [book])

  function sortBy(key, numeric) {
    setSort((s) => (s.key === key ? { key, dir: -s.dir } : { key, dir: numeric ? -1 : 1 })) // numbers: high first
  }

  if (book.topics.length === 0) {
    return (
      <div className="lp-card tc-empty">
        <b>Add a topic to start grading.</b>
        <p className="lp-muted">A topic is what you want students to teach Reeta, with notes her quizzes are written from.</p>
        <button className="lp-btn lp-btn-primary tc-empty-btn" onClick={onTopics}>Add a topic</button>
      </div>
    )
  }

  return (
    <>
      <div className="tc-stats">
        <Stat label="Class average" value={pct(totals.average)} />
        <Stat label="Topics passed" value={`${totals.passed} / ${totals.cells}`} />
        <Stat label="Took a quiz this week" value={`${totals.activeWeek} / ${book.students.length}`} />
        <Stat label="Need a look" value={totals.attention} warn={totals.attention > 0} />
      </div>

      {book.students.length === 0 ? (
        <div className="lp-card tc-empty">
          <b>No students yet.</b>
          <p className="lp-muted">Students sign up, open <b>My classes</b>, and enter <b>{book.class.join_code}</b>.</p>
        </div>
      ) : (
        <div className="lp-card tc-table-wrap">
          <table className="tc-table">
            <thead>
              <tr>
                {columns.map(([key, label, , numeric, topicId]) => (
                  <th key={key} className={`${numeric ? 'is-num' : ''} ${topicId ? 'is-topic' : ''}`}
                    aria-sort={sort.key === key ? (sort.dir > 0 ? 'ascending' : 'descending') : 'none'}>
                    <button onClick={() => sortBy(key, numeric)} title={topicId ? `Sort by ${label}` : undefined}>
                      {label}<span className="tc-sort" aria-hidden="true">{sort.key === key ? (sort.dir > 0 ? '▲' : '▼') : ''}</span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const { student, summary: s } = r
                const flag = attention(r)
                return (
                  <tr key={student.id} onClick={() => onStudent(student.id)}>
                    <td>
                      <button className="tc-student" onClick={(e) => { e.stopPropagation(); onStudent(student.id) }}>{student.name}</button>
                      {flag && <span className={`tc-flag is-${flag.toLowerCase().replace(' ', '-')}`}>{flag}</span>}
                      <div className="lp-muted">{student.email}</div>
                    </td>
                    {book.topics.map((t) => <td key={t.id} className="is-topic"><TopicCell p={r.topics[String(t.id)]} /></td>)}
                    <td className="is-num">{pct(s.average_percent)}</td>
                    <td>{relativeDay(s.last_active)}</td>
                    <td className="is-num">{s.quizzes ? s.wrong : '—'}</td>
                    <td className="is-num">{s.quizzes ? s.not_taught : '—'}</td>
                    <td className="is-num">{r.practice.quizzes ? `${r.practice.quizzes} quiz${r.practice.quizzes === 1 ? '' : 'zes'}` : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="lp-muted tc-legend">
        Each topic shows where the student is and their best score. <b>Taught wrong</b>: they covered it but explained it
        incorrectly (a misconception). <b>Never taught</b>: they skipped it (a gap). Averages and counts are across topics;
        free practice is not graded.
      </p>
    </>
  )
}

export function TopicCell({ p }) {
  return (
    <span className="tc-cell">
      <span className={`tc-status is-${p.status}`}>{STATUS_LABEL[p.status]}</span>
      {p.best_percent !== null && <span className="tc-cell-best">best {p.best_percent}%</span>}
    </span>
  )
}

export function Back({ onBack, label = 'All classes' }) {
  return <button className="lp-link tc-back" onClick={onBack}>← {label}</button>
}

export function Stat({ label, value, warn = false }) {
  return (
    <div className={`lp-card tc-stat ${warn ? 'is-warn' : ''}`}>
      <span className="tc-stat-value">{value}</span>
      <span className="tc-stat-label">{label}</span>
    </div>
  )
}
