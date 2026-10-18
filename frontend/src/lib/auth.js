// The logged in account: {token, user: {id, email, name, role}} in localStorage, or null for the anonymous
// demo session. Every storage access is guarded (private windows can block it).
const KEY = 'reeta_auth'
const listeners = new Set()

export function readAuth() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || 'null')
    return v?.token && v?.user ? v : null
  } catch { return null }
}

export function saveAuth(auth) {
  try { localStorage.setItem(KEY, JSON.stringify(auth)) } catch { /* storage blocked: logged in for this tab only */ }
  memory = auth
  listeners.forEach((fn) => fn(auth))
}

export function clearAuth() {
  try { localStorage.removeItem(KEY) } catch { /* storage blocked */ }
  setActiveTopic(null)
  memory = null
  listeners.forEach((fn) => fn(null))
}


// Falls back to memory so a blocked localStorage still keeps the login for this tab.
let memory = readAuth()
export const currentAuth = () => memory
export const token = () => memory?.token || null

// The topic a logged in student is teaching Reeta (sent as X-Topic-Id), or null for free practice.
// Each topic has its own Reeta on the backend. Kept per tab, so a reload stays on the same topic.
const TOPIC_KEY = 'reeta_topic'
let topic = (() => { try { return Number(sessionStorage.getItem(TOPIC_KEY)) || null } catch { return null } })()
export const activeTopic = () => (memory ? topic : null)
export function setActiveTopic(id) {
  topic = id || null
  try { topic ? sessionStorage.setItem(TOPIC_KEY, String(topic)) : sessionStorage.removeItem(TOPIC_KEY) } catch { /* blocked */ }
}

export function onAuthChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
