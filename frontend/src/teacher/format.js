// Display helpers for the gradebook. The backend sends UTC times as 'YYYY-MM-DD HH:MM:SS'.

export function parseUtc(s) {
  if (!s) return null
  const d = new Date(`${String(s).replace(' ', 'T')}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

function dayDiff(d, now = new Date()) {
  const start = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  return Math.round((start(now) - start(d)) / 86400000)
}

export function daysAgo(s) {
  const d = parseUtc(s)
  return d ? dayDiff(d) : null
}

// "today", "yesterday", "3 days ago", then a date
export function relativeDay(s) {
  const d = parseUtc(s)
  if (!d) return 'never'
  const n = dayDiff(d)
  if (n <= 0) return 'today'
  if (n === 1) return 'yesterday'
  if (n < 7) return `${n} days ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' })
}

export function dateTime(s) {
  const d = parseUtc(s)
  return d ? d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''
}

export const pct = (v) => (v === null || v === undefined ? '—' : `${v}%`)

export const INACTIVE_DAYS = 7
export const STRUGGLING_PCT = 50

// Why a student needs a look, or null. Shown as a flag in the roster. row: a gradebook student row.
// "Not started" only when every topic is untouched; teaching without a quiz yet is a start.
export function attention({ summary, topics = {} }) {
  if (!summary.quizzes) return Object.values(topics).some((p) => p.status !== 'not_started') ? null : 'Not started'
  if (daysAgo(summary.last_active) >= INACTIVE_DAYS) return 'Inactive'
  if (summary.average_percent < STRUGGLING_PCT) return 'Struggling'
  return null
}

export const RESULT_LABEL = { correct: 'Correct', wrong: 'Taught wrong', not_taught: 'Never taught' }
