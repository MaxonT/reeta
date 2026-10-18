// All calls go through the Vite proxy (/api -> backend). Keys never reach the browser.

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
    const res = await fetch(`/api/exam/run?questions=${questions}`, { method: 'POST', headers: { 'X-Session-Id': SESSION }, signal })
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
