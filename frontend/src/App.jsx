import { useEffect, useState } from 'react'
import Loop from './loop/Loop.jsx'
import ClassroomApp from './ClassroomApp.jsx'
import Login from './auth/Login.jsx'
import TeacherApp from './teacher/TeacherApp.jsx'
import { api } from './lib/api.js'
import { clearAuth, currentAuth, onAuthChange, saveAuth } from './lib/auth.js'

// Default: the daily loop (Home, Teach, Quiz, Result). The old six scenes live at #classroom.
// Logged out: Login. Students get the loop on their account, teachers the gradebook dashboard.
// "Try it without an account", #demo and #classroom use the anonymous session as before.
const viewFromHash = () => (window.location.hash === '#classroom' ? 'classroom' : 'loop')
const GUEST_KEY = 'reeta_guest'
const readGuest = () => {
  if (['#demo', '#classroom'].includes(window.location.hash)) return true
  try { return sessionStorage.getItem(GUEST_KEY) === '1' } catch { return false }
}

export default function App() {
  const [view, setView] = useState(viewFromHash)
  const [auth, setAuthState] = useState(currentAuth)
  const [guest, setGuest] = useState(readGuest)
  useEffect(() => {
    const onHash = () => { setView(viewFromHash()); if (readGuest()) setGuest(true) }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => onAuthChange(setAuthState), [])
  // Refresh the stored user (a 401 here logs out, see api.js).
  useEffect(() => {
    if (auth) api.me().then(({ user }) => saveAuth({ ...auth, user })).catch(() => {})
  }, [auth?.token])

  const go = (v) => { window.location.hash = v === 'classroom' ? 'classroom' : ''; setView(v) }
  function enterGuest(on) {
    try { on ? sessionStorage.setItem(GUEST_KEY, '1') : sessionStorage.removeItem(GUEST_KEY) } catch { /* blocked */ }
    setGuest(on)
  }
  async function logout() {
    await api.logout().catch(() => {})
    clearAuth()
  }

  if (auth?.user.role === 'teacher') return <TeacherApp user={auth.user} onLogout={logout} />
  if (!auth && !guest) return <Login onGuest={() => enterGuest(true)} />
  return view === 'classroom'
    ? <ClassroomApp onExit={() => go('loop')} />
    : <Loop key={auth?.user.id || 'guest'} account={auth?.user || null} onLogout={logout}
        onSignIn={auth ? undefined : () => enterGuest(false)} />
}
