// Fallbacks for the daily loop endpoints (POST /loop/quiz, GET /loop/today), built only from the
// existing endpoints. The streak lives in localStorage here, so every storage access is guarded.
import { levelFor, lines } from './reetaLines.js'

const MAX_QUESTIONS = 3

// ---------- streak in localStorage ----------
function storeKey() {
  let s = 'demo'
  try { s = localStorage.getItem('reeta_session') || 'demo' } catch { /* storage blocked */ }
  return `reeta_loop_${s}`
}
export function readLoopState() {
  try {
    const v = JSON.parse(localStorage.getItem(storeKey()) || '{}')
    return { streak: v.streak || 0, best: v.best || 0, lastPassDay: v.lastPassDay || null }
  } catch { return { streak: 0, best: 0, lastPassDay: null } }
}
function writeLoopState(v) {
  try { localStorage.setItem(storeKey(), JSON.stringify(v)) } catch { /* storage blocked */ }
}

export function dayKey(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function daysBetween(a, b) {
  if (!a) return null
  const [y1, m1, d1] = a.split('-').map(Number), [y2, m2, d2] = b.split('-').map(Number)
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000)
}

// Current streak: alive if the last pass was today or yesterday.
function liveStreak(st = readLoopState()) {
  const days = daysBetween(st.lastPassDay, dayKey())
  return { days, streak: days === null || days > 1 ? 0 : st.streak }
}

// A pass counts once per day.
function recordPass() {
  const st = readLoopState()
  const { days, streak } = liveStreak(st)
  if (days === 0) return streak
  const next = streak + 1
  writeLoopState({ streak: next, best: Math.max(st.best, next), lastPassDay: dayKey() })
  return next
}

// ---------- shapes ----------
export function streakCount(s) {
  if (typeof s === 'number') return s
  if (s && typeof s === 'object') return s.count ?? s.current ?? s.streak ?? 0
  return 0
}
function levelName(l, mastered, total) {
  if (typeof l === 'string' && l) return l
  if (typeof l === 'number') return levelFor(l, total)
  if (l && typeof l === 'object') return l.name || l.label || levelFor(mastered, total)
  return levelFor(mastered, total)
}

export function normalizeToday(t) {
  const progress = { mastered: t.progress?.mastered ?? 0, total: t.progress?.total ?? 5 }
  return {
    ...t,
    streak: streakCount(t.streak),
    best_streak: streakCount(t.best_streak),
    mood: t.mood || 'listening',
    progress,
    level: levelName(t.level, progress.mastered, progress.total),
    source: 'loop',
  }
}

export function normalizeQuiz(q) {
  const results = (q.results || []).slice(0, MAX_QUESTIONS)
  const score = q.score ?? results.filter((r) => r.is_correct).length
  const total = q.total ?? results.length
  const passed = q.passed ?? score === total
  return {
    ...q, results, score, total, passed,
    mood: q.mood || (passed ? 'proud' : 'confused'),
    result_line: q.result_line || (passed ? lines.pass : lines.fail),
    streak: q.streak === undefined ? null : streakCount(q.streak),
    source: 'loop',
  }
}

// ---------- GET /loop/today fallback ----------
export async function todayFallback(api) {
  const nb = await api.notebook()
  const concepts = nb.concepts || []
  const mastered = concepts.filter((c) => c.status === 'correct').length
  const weakest = concepts.find((c) => c.status === 'misconception') || concepts.find((c) => c.status === 'missing') || null
  const st = readLoopState()
  const { days, streak } = liveStreak(st)
  let mood = 'listening'
  if (days === 0) mood = 'proud'
  else if (days !== null && days > 1) mood = 'sad'
  else if (weakest?.status === 'misconception') mood = 'confused'
  const ask = weakest ? { concept_id: weakest.id, label: weakest.label, reason: weakest.status } : null
  return {
    streak,
    best_streak: Math.max(st.best, streak),
    days_since_last: days,
    mood,
    ask,
    line: lines.home({ mood, ask, quote: weakest?.entry?.sentence?.text }),
    progress: { mastered, total: concepts.length || 5 },
    level: levelFor(mastered, concepts.length || 5),
    concepts: concepts.map((c) => ({ id: c.id, label: c.label, status: c.status })),
    source: 'fallback',
  }
}

// ---------- POST /loop/quiz fallback ----------
// Take the full Exam, keep up to 3 results. Priority:
//   1. questions about concepts in the latest lecture that Reeta can fully answer from her Notebook
//   2. other questions she can fully answer
//   3. only if nothing above exists: questions needing concepts she was never taught
// Wrong answers first inside each group, so the round always tests what she got wrong.
export async function quizFallback(api, { concept_ids } = {}) {
  let latest = concept_ids
  if (!latest?.length) latest = await latestConcepts(api)
  const latestSet = new Set(latest || [])
  const exam = await api.takeExam()
  const all = exam.results.map((r, i) => {
    const req = r.question?.required_concepts || r.concept_ids || []
    const touchesLatest = req.some((c) => latestSet.has(c))
    const covered = r.reason !== 'not_taught'
    const tier = touchesLatest && covered ? 0 : covered ? 1 : touchesLatest ? 2 : 3
    return { r, i, tier }
  })
  let pool = all.filter((x) => x.tier <= 1)
  if (!pool.length) pool = all
  pool.sort((a, b) => a.tier - b.tier || Number(a.r.is_correct) - Number(b.r.is_correct) || a.i - b.i)
  const results = pool.slice(0, MAX_QUESTIONS).sort((a, b) => a.i - b.i).map((x) => x.r)
  const score = results.filter((r) => r.is_correct).length
  const passed = results.length > 0 && score === results.length
  const prev = liveStreak().streak
  const streak = passed ? recordPass() : prev
  return {
    round_id: `exam-${exam.attempt_id}`,
    score, total: results.length, passed,
    mood: passed ? 'proud' : 'confused',
    result_line: passed ? lines.pass : lines.fail,
    results,
    streak,
    source: 'fallback',
  }
}

async function latestConcepts(api) {
  try {
    const nb = await api.notebook()
    const entries = nb.entries || []
    const last = Math.max(...entries.map((e) => e.sentence?.lecture_id ?? -1))
    return entries.filter((e) => e.sentence?.lecture_id === last).map((e) => e.concept_id)
  } catch { return [] }
}
