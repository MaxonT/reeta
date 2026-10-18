import { useMemo } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

// Reeta, the AI student. Four faces by Semi (public/teachback). "sad" has no asset yet, so it uses
// the confused face with a droopier pose. `cheer` and `hmm` reuse the proud and thinking faces and
// add little overlays (sparkles, hearts, a sweat drop, a question mark) so every mood reads clearly.
const FACES = { listening: 'listening', thinking: 'thinking', hmm: 'thinking', confused: 'confused', proud: 'proud', happy: 'proud', cheer: 'proud', sad: 'confused' }
const BASE = `${import.meta.env.BASE_URL}teachback/`

const ALT = {
  listening: 'Reeta, listening closely',
  thinking: 'Reeta, thinking hard',
  hmm: 'Reeta, wondering',
  confused: 'Reeta, confused',
  proud: 'Reeta, proud and happy',
  cheer: 'Reeta, cheering',
  sad: 'Reeta, a little sad',
}

// One shot reactions when the face changes; a gentle float while idle.
function motionFor(mood, idle) {
  if (mood === 'cheer') return { animate: { y: [0, -26, 0, -14, 0], rotate: [0, -6, 6, -3, 0] }, transition: { duration: 0.9, ease: 'easeOut' } }
  if (mood === 'proud' || mood === 'happy') return { animate: { y: [0, -18, 0, -6, 0], rotate: [0, -3, 3, 0] }, transition: { duration: 0.75, ease: 'easeOut' } }
  if (mood === 'confused') return { animate: { rotate: [0, -5, 4, -2, 0], x: [0, -3, 3, 0] }, transition: { duration: 0.7 } }
  if (mood === 'hmm') return { animate: { rotate: [0, 6, 6, 0] }, transition: { duration: 0.9, ease: 'easeInOut' } }
  if (mood === 'sad') return { animate: { y: 4, rotate: -3 }, transition: { duration: 0.8 } }
  if (mood === 'thinking') return { animate: { y: [0, -3, 0] }, transition: { duration: 1.2, repeat: Infinity, ease: 'easeInOut' } }
  if (idle) return { animate: { y: [0, -6, 0] }, transition: { duration: 3.4, repeat: Infinity, ease: 'easeInOut' } }
  return { animate: { y: 0 }, transition: {} }
}

// Floating emoji cues around her head. `kind` decides the set; each piece drifts up and fades.
const CUES = {
  celebrate: { glyphs: ['✨', '⭐', '💛', '✨', '🎉', '⭐'], rise: -70 },
  hearts: { glyphs: ['💛', '💚', '💛', '✨'], rise: -80 },
  oops: { glyphs: ['💧'], rise: 14 },
  hmm: { glyphs: ['❓'], rise: -26 },
  sad: { glyphs: ['💧'], rise: 20 },
}
const cueFor = (mood) => ({ proud: 'celebrate', happy: 'celebrate', cheer: 'hearts', confused: 'oops', hmm: 'hmm', sad: 'sad' })[mood] || null

function Cues({ mood, size }) {
  const kind = cueFor(mood)
  const bits = useMemo(() => {
    const cue = kind && CUES[kind]
    if (!cue) return []
    return cue.glyphs.map((g, i) => {
      const side = i % 2 ? 1 : -1
      return { g, x: side * (size * (0.28 + 0.1 * (i % 3))), y0: -size * (0.1 + 0.07 * i), rise: cue.rise - i * 6, delay: 0.05 * i, s: 0.9 + (i % 3) * 0.2 }
    })
  }, [kind, mood, size])
  if (!bits.length) return null
  return (
    <div className="lp-cues" aria-hidden="true">
      {bits.map((b, i) => (
        <motion.span key={`${mood}-${i}`} className="lp-cue" style={{ fontSize: Math.max(16, size * 0.12) * b.s }}
          initial={{ opacity: 0, x: b.x, y: b.y0, scale: 0.4 }}
          animate={{ opacity: [0, 1, 1, 0], x: b.x, y: b.y0 + b.rise, scale: [0.4, 1.15, 1, 0.9] }}
          transition={{ duration: 1.6, delay: b.delay, ease: 'easeOut' }}>{b.g}</motion.span>
      ))}
    </div>
  )
}

export default function Reeta({ mood = 'listening', size = 200, say, idle = true, pulse = false }) {
  const reduce = useReducedMotion()
  const face = FACES[mood] || 'listening'
  const m = reduce ? { animate: {}, transition: {} } : motionFor(mood, idle)
  return (
    <div className="lp-reeta">
      <div className="lp-bubble-slot" aria-live="polite">
        <AnimatePresence mode="wait">
          {say && (
            <motion.p key={say} className="lp-bubble"
              initial={{ opacity: 0, y: 6, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.22 }}>
              {say}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
      <div className={`lp-avatar ${pulse ? 'is-pulsing' : ''}`} style={{ width: size, height: size }}>
        <span className="lp-halo" aria-hidden="true" />
        <motion.img key={face + mood} src={`${BASE}student-${face}.svg`} alt={ALT[mood] || ALT.listening}
          width={size} height={size} draggable="false"
          initial={reduce ? false : { scale: 0.92, opacity: 0.6 }}
          animate={{ scale: 1, opacity: 1, ...m.animate }}
          transition={{ ...m.transition, scale: { duration: 0.25 }, opacity: { duration: 0.25 } }} />
        {!reduce && <Cues mood={mood} size={size} />}
      </div>
    </div>
  )
}
