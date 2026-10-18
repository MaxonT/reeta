import { useState } from 'react'
import { api, errorDetail } from '../lib/api.js'
import { saveAuth } from '../lib/auth.js'
import Reeta from '../loop/Reeta.jsx'
import '../loop/loop.css'
import './account.css'

// Log in or sign up. Students teach Reeta; teachers see their classes' gradebooks.
// "Try it without an account" keeps the old anonymous demo session.
export default function Login({ onGuest }) {
  const [mode, setMode] = useState('signup') // signup | login
  const [role, setRole] = useState('student')
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const signup = mode === 'signup'

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const out = signup
        ? await api.signup({ ...form, role })
        : await api.login({ email: form.email, password: form.password })
      saveAuth(out) // App switches screens on this
    } catch (err) {
      setError(errorDetail(err) || 'Could not reach Reeta. Is the backend running?')
      setBusy(false)
    }
  }

  return (
    <div className="lp-app">
      <div className="lp-phone">
        <div className="lp-top"><div className="lp-brand">Reeta</div></div>
        <form className="lp-body ac-login" onSubmit={submit} noValidate>
          <Reeta mood="listening" size={132}
            say={signup ? (role === 'teacher' ? 'Make a class, and see how your students teach me.' : 'Teach me, and I’ll show you what you really know.') : 'Welcome back!'} />

          <div className="ac-tabs" role="tablist" aria-label="Log in or sign up">
            <button type="button" role="tab" aria-selected={signup} className={signup ? 'is-on' : ''}
              onClick={() => { setMode('signup'); setError(null) }}>Sign up</button>
            <button type="button" role="tab" aria-selected={!signup} className={!signup ? 'is-on' : ''}
              onClick={() => { setMode('login'); setError(null) }}>Log in</button>
          </div>

          {signup && (
            <fieldset className="ac-roles">
              <legend className="lp-section-label">I’m a</legend>
              {[['student', 'Student', 'I teach Reeta'], ['teacher', 'Teacher', 'I run a class']].map(([value, label, sub]) => (
                <label key={value} className={`ac-role ${role === value ? 'is-on' : ''}`}>
                  <input type="radio" name="role" value={value} checked={role === value} onChange={() => setRole(value)} />
                  <b>{label}</b><span>{sub}</span>
                </label>
              ))}
            </fieldset>
          )}

          <div className="ac-fields">
            {signup && (
              <label className="ac-field">
                <span>Name</span>
                <input value={form.name} onChange={set('name')} autoComplete="name" required maxLength={200} />
              </label>
            )}
            <label className="ac-field">
              <span>Email</span>
              <input type="email" value={form.email} onChange={set('email')} autoComplete="email" required />
            </label>
            <label className="ac-field">
              <span>Password</span>
              <input type="password" value={form.password} onChange={set('password')} required
                autoComplete={signup ? 'new-password' : 'current-password'} minLength={signup ? 8 : undefined} />
              {signup && <small>At least 8 characters</small>}
            </label>
          </div>

          {error && <p className="lp-error" role="alert">{error}</p>}

          <button className="lp-btn lp-btn-primary lp-btn-xl ac-submit" disabled={busy}>
            {busy ? 'One moment…' : signup ? 'Create account' : 'Log in'}
          </button>
          <button type="button" className="lp-link" onClick={onGuest}>Try it without an account</button>
        </form>
      </div>
    </div>
  )
}
