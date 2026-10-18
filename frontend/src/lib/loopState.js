// Daily loop state the backend does not keep: the streak and the last quiz result. It lives in
// localStorage per session, so every storage access is guarded (private windows can block it).
import { SESSION } from './api.js'

const KEY = `reeta_loop_${SESSION}`
const EMPTY = { streak: 0, best: 0, lastPassDay: null, last: null } // last: {day, score, total, passed}

export function readLoopState() {
  try { return { ...EMPTY, ...JSON.parse(localStorage.getItem(KEY) || '{}') } } catch { return { ...EMPTY } }
}
function write(v) {
  try { localStorage.setItem(KEY, JSON.stringify(v)) } catch { /* storage blocked */ }
}
export function clearLoopState() {
  try { localStorage.removeItem(KEY) } catch { /* storage blocked */ }
}

export function dayKey(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function daysSince(day) {
  if (!day) return null
  const [y, m, d] = day.split('-').map(Number)
  const now = new Date()
  return Math.round((Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - Date.UTC(y, m - 1, d)) / 86400000)
}

// What Home shows: the live streak (alive if the last pass was today or yesterday) and Reeta's mood.
// Mood: sad after 2+ days away, confused if the last quiz failed, proud if she passed today, else listening.
export function today() {
  const st = readLoopState()
  const sincePass = daysSince(st.lastPassDay)
  const streak = sincePass === null || sincePass > 1 ? 0 : st.streak
  const sinceLast = daysSince(st.last?.day)
  let mood = 'listening'
  if (sinceLast !== null && sinceLast >= 2) mood = 'sad'
  else if (st.last && !st.last.passed) mood = 'confused'
  else if (sincePass === 0) mood = 'proud'
  return { streak, best: Math.max(st.best, streak), mood, last: st.last }
}

// Record a finished quiz. A pass counts once per day. Returns the streak after this quiz.
export function recordQuiz({ score, total, passed }) {
  const st = readLoopState()
  const { streak } = today()
  let next = streak
  if (passed && daysSince(st.lastPassDay) !== 0) next = streak + 1
  write({
    streak: passed ? next : st.streak,
    best: Math.max(st.best, next),
    lastPassDay: passed ? dayKey() : st.lastPassDay,
    last: { day: dayKey(), score, total, passed },
  })
  return next
}
