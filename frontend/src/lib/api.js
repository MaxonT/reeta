// All calls go through the Vite proxy (/api -> backend). Keys never reach the browser.
import { activeTopic, clearAuth, token } from './auth.js'

// Where the backend lives. Set VITE_API_BASE_URL at build time (e.g. https://my-backend.up.railway.app/api)
// to host the frontend separately. Unset, it is the same-origin /api (Vite dev proxy or the Docker image).
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

export const SESSION = (() => { try { return localStorage.getItem('reeta_session') || 'demo' } catch { return 'demo' } })()

// Logged in: the account's token, and the backend uses the account's data (the active topic's, if one is
// picked). Otherwise the anonymous session.
export function authHeaders() {
  const t = token()
  if (!t) return { 'X-Session-Id': SESSION }
  return activeTopic() ? { Authorization: `Bearer ${t}`, 'X-Topic-Id': String(activeTopic()) } : { Authorization: `Bearer ${t}` }
}

// A 401 while logged in means the login expired: drop it so the app shows the login screen.
function checkAuth(res) {
  if (res.status === 401 && token()) clearAuth()
}

async function req(method, path, body) {
  const opts = { method, headers: authHeaders() }
  if (body instanceof FormData) opts.body = body
  else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(`/api${path}`, opts)
  checkAuth(res)
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status} ${await res.text()}`)
  return res.json()
}

// req() throws "POST /path: 400 {"detail": "..."}"; this pulls out the backend's own message.
export function errorDetail(e) {
  const m = /\{.*\}$/s.exec(e?.message || '')
  try { return m ? JSON.parse(m[0]).detail : null } catch { return null }
}

export const api = {
  // Accounts (see backend/app/accounts.py)
  signup: (body) => req('POST', '/auth/signup', body),
  login: (body) => req('POST', '/auth/login', body),
  logout: () => req('POST', '/auth/logout'),
  me: () => req('GET', '/auth/me'),
  myProgress: () => req('GET', '/me/progress'),
  createClass: (name) => req('POST', '/classes', { name }),
  joinClass: (joinCode) => req('POST', '/classes/join', { join_code: joinCode }),
  gradebook: (classId) => req('GET', `/classes/${classId}/gradebook`),
  // Topics (see backend/app/classwork.py)
  myTopics: () => req('GET', '/me/topics'),
  topic: (id) => req('GET', `/topics/${id}`),
  classTopics: (classId) => req('GET', `/classes/${classId}/topics`),
  createTopic: (classId, body) => req('POST', `/classes/${classId}/topics`, body),
  updateTopic: (id, body) => req('PATCH', `/topics/${id}`, body),
  addTopicNotes: (id, { file, text }) => {
    const fd = new FormData()
    if (file) fd.append('file', file)
    if (text) fd.append('text', text)
    return req('POST', `/topics/${id}/notes`, fd)
  },
  deleteTopicNotes: (id, noteId) => req('DELETE', `/topics/${id}/notes/${noteId}`),
  studentGrades: (classId, studentId) => req('GET', `/classes/${classId}/students/${studentId}`),

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
  audioUrl: (lectureId) => `${API_BASE}/lectures/${lectureId}/audio`,

  // Source material the exam questions are written from (.txt, .md or pasted text). Per session.
  sources: () => req('GET', '/sources'),
  postSource: ({ file, text }) => {
    const fd = new FormData()
    if (file) fd.append('file', file)
    if (text) fd.append('text', text)
    return req('POST', '/sources', fd)
  },
  deleteSource: (id) => req('DELETE', `/sources/${id}`),

  // The live exam: POST /exam/run streams Server-Sent Events (see FRONTEND_CHANGES.md).
  // onEvent(name, data) is called for each event in order. Resolves when the stream ends.
  // EventSource cannot POST, so this reads the body stream by hand. Abort with signal.
  runExam: async (onEvent, { questions = 3, signal } = {}) => {
    const res = await fetch(`/api/exam/run?questions=${questions}`, { method: 'POST', headers: authHeaders(), signal })
    checkAuth(res)
    if (!res.ok || !res.body) throw new Error(`POST /exam/run: ${res.status} ${await res.text()}`)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let cut
      while ((cut = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, cut)
        buf = buf.slice(cut + 2)
        let name = 'message', data = ''
        for (const line of block.split('\n')) {
          if (line.startsWith('event:')) name = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (data) onEvent(name, JSON.parse(data))
      }
    }
  },
}
