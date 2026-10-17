// All calls go through the Vite proxy (/api -> backend). Keys never reach the browser.
const SESSION = localStorage.getItem('reeta_session') || 'demo'

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
}
