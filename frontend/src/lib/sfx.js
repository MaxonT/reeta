// Reeta's sound effects, synthesized with Web Audio so there are no files to load. Sounds are warm
// and short: wrong answers are a soft "aww", never a harsh buzzer. A mute toggle persists in
// localStorage (every access guarded, private windows can block it).

const KEY = 'reeta_sfx_muted'
let ctx = null
let muted = false
try { muted = localStorage.getItem(KEY) === '1' } catch { /* storage blocked */ }
const listeners = new Set()

export const isMuted = () => muted
export function setMuted(v) {
  muted = !!v
  try { localStorage.setItem(KEY, muted ? '1' : '0') } catch { /* storage blocked */ }
  listeners.forEach((fn) => fn(muted))
}
export function onMutedChange(fn) { listeners.add(fn); return () => listeners.delete(fn) }

function audio() {
  const AC = window.AudioContext || window.webkitAudioContext
  if (!AC) return null
  ctx = ctx || new AC()
  if (ctx.state === 'suspended') ctx.resume().catch(() => {})
  return ctx
}

// Browsers keep audio suspended until the person touches the page. Unlock on the first gesture so
// sounds that fire later (after an upload, after the judge grades) are still heard.
if (typeof window !== 'undefined') {
  const unlock = () => { audio(); ['pointerdown', 'keydown'].forEach((e) => window.removeEventListener(e, unlock)) }
  ;['pointerdown', 'keydown'].forEach((e) => window.addEventListener(e, unlock))
}

// One note: a sine/triangle with a quick attack and a smooth decay. `glide` slides the pitch.
function tone(freq, start, dur, { type = 'sine', gain = 0.16, glide = null } = {}) {
  const c = audio()
  if (!c) return
  const t = c.currentTime + start
  const osc = c.createOscillator()
  const g = c.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t)
  if (glide) osc.frequency.exponentialRampToValueAtTime(glide, t + dur)
  g.gain.setValueAtTime(0.0001, t)
  g.gain.exponentialRampToValueAtTime(gain, t + 0.02)
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
  osc.connect(g).connect(c.destination)
  osc.start(t)
  osc.stop(t + dur + 0.05)
}

const N = { C5: 523.25, D5: 587.33, E5: 659.25, G5: 783.99, A5: 880, C6: 1046.5, E6: 1318.5, G4: 392, E4: 329.63, D4: 293.66, C4: 261.63, A4: 440 }

const SOUNDS = {
  // Lesson saved: two quick rising pings.
  sent() { tone(N.G5, 0, 0.18); tone(N.C6, 0.1, 0.3) },
  // Recording starts / stops: tiny ticks so holding the mic feels responsive.
  micOn() { tone(N.E5, 0, 0.1, { type: 'triangle', gain: 0.1 }) },
  micOff() { tone(N.C5, 0, 0.12, { type: 'triangle', gain: 0.1 }) },
  // Right answer: bright "ding ding".
  correct() { tone(N.E5, 0, 0.2); tone(N.A5, 0.09, 0.2); tone(N.E6, 0.18, 0.45, { gain: 0.13 }) },
  // Wrong answer: a gentle falling "aww", two soft low notes.
  wrong() { tone(N.G4, 0, 0.25, { type: 'triangle', gain: 0.17, glide: N.E4 }); tone(N.D4, 0.2, 0.45, { type: 'triangle', gain: 0.15, glide: 196 }) },
  // Never taught: a curious little "hmm?" that ends upward.
  notTaught() { tone(N.D4 * 1.5, 0, 0.16, { type: 'triangle', gain: 0.12 }); tone(N.A4 * 1.1, 0.14, 0.3, { type: 'triangle', gain: 0.12 }) },
  // Passed the quiz: a happy arpeggio fanfare with a sparkle on top.
  pass() {
    ;[N.C5, N.E5, N.G5, N.C6].forEach((f, i) => tone(f, i * 0.11, 0.28, { type: 'triangle', gain: 0.15 }))
    tone(N.G5, 0.5, 0.7, { gain: 0.1 }); tone(N.C6, 0.5, 0.7, { gain: 0.1 }); tone(N.E6, 0.5, 0.8, { gain: 0.1 })
    tone(N.E6, 0.9, 0.5, { gain: 0.07 })
  },
  // Did not pass: soft, kind descending phrase (she is sad, not scolded).
  fail() { [N.A4, N.G4, N.E4, N.D4].forEach((f, i) => tone(f, i * 0.16, 0.34, { type: 'triangle', gain: 0.13 })) },
}

export function play(name) {
  if (muted || !SOUNDS[name]) return
  try { SOUNDS[name]() } catch { /* audio is a bonus, never break the app */ }
}

// Sound for a graded question, by outcome.
export function playGrade(q) {
  play(q.is_correct ? 'correct' : q.reason === 'not_taught' ? 'notTaught' : 'wrong')
}
