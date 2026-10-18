// All calls go through the Vite proxy (/api -> backend). Keys never reach the browser.
import { quizFallback, todayFallback, normalizeQuiz, normalizeToday } from './loopFallback.js'

export const SESSION = (() => { try { return localStorage.getItem('reeta_session') || 'demo' } catch { return 'demo' } })()

async function req(method, path, body) {
  const opts = { method, headers: { 'X-Session-Id': SESSION } }
  if (body instanceof FormData) opts.body = body
  else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(`/api${path}`, opts)
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status} ${await res.text()}`)
  return res.json()
}

export const api = {
  answerKey: () => req('GET', '/answer-key'),
  notebook: () => req('GET', '/notebook'),
  searchNotebook: (q = '', conceptId) => req('GET', `/notebook/search?q=${encodeURIComponent(q)}${conceptId ? `&concept_id=${encodeURIComponent(conceptId)}` : ''}`),
  conceptEdges: () => req('GET', '/concepts/edges'),
  lectures: () => req('GET', '/lectures'),
  postLecture: ({ blob, kind, sentences, text }) => {
    const fd = new FormData()
    if (blob) fd.append('audio', blob, `lecture${blob.type.includes('ogg') ? '.ogg' : blob.type.includes('mp4') ? '.mp4' : '.webm'}`)
    fd.append('kind', kind)
    if (sentences?.length) fd.append('transcript', JSON.stringify(sentences))
    if (text) fd.append('text', text)
    return req('POST', '/lectures/audio', fd)
  },
  confirm: (lectureId, body) => req('POST', `/lectures/${lectureId}/confirm`, body),
  takeExam: () => req('POST', '/exam/take'),
  officeHours: () => req('GET', '/office-hours'),
  report: () => req('GET', '/report'),
  reset: () => req('POST', '/session/reset'),
  audioUrl: (lectureId) => `/api/lectures/${lectureId}/audio`,

  // Daily loop. The /loop endpoints come from a parallel backend PR. Until they exist (or if they fail),
  // both fall back to the endpoints above so the loop always works.
  // opts: { lecture_id, concept_ids } of the lecture just taught, used to pick today's questions.
  loopQuiz: async (opts = {}) => {
    try {
      return normalizeQuiz(await req('POST', '/loop/quiz', opts))
    } catch (e) {
      console.warn('[loop] /loop/quiz unavailable, using /exam/take fallback:', e.message)
      return quizFallback(api, opts)
    }
  },
  loopToday: async () => {
    try {
      return normalizeToday(await req('GET', '/loop/today'))
    } catch (e) {
      console.warn('[loop] /loop/today unavailable, computing from /notebook:', e.message)
      return todayFallback(api)
    }
  },
}
