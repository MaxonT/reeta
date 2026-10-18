import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

// Reeta, the AI student. Four faces by Semi (public/teachback). "sad" has no asset yet, so it uses
// the confused face with a droopier pose.
const FACES = { listening: 'listening', thinking: 'thinking', confused: 'confused', proud: 'proud', happy: 'proud', sad: 'confused' }
const BASE = `${import.meta.env.BASE_URL}teachback/`

const ALT = {
  listening: 'Reeta, listening closely',
  thinking: 'Reeta, thinking hard',
  confused: 'Reeta, confused',
  proud: 'Reeta, proud and happy',
  sad: 'Reeta, a little sad',
}

// One shot reactions when the face changes; a gentle float while idle.
function motionFor(mood, idle) {
  if (mood === 'proud' || mood === 'happy') return { animate: { y: [0, -14, 0], rotate: [0, -2, 2, 0] }, transition: { duration: 0.6, ease: 'easeOut' } }
  if (mood === 'confused') return { animate: { rotate: [0, -4, 3, 0] }, transition: { duration: 0.6 } }
  if (mood === 'sad') return { animate: { y: 4, rotate: -3 }, transition: { duration: 0.8 } }
  if (mood === 'thinking') return { animate: { y: [0, -3, 0] }, transition: { duration: 1.2, repeat: Infinity, ease: 'easeInOut' } }
  if (idle) return { animate: { y: [0, -6, 0] }, transition: { duration: 3.4, repeat: Infinity, ease: 'easeInOut' } }
  return { animate: { y: 0 }, transition: {} }
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
          initial={reduce ? false : { scale: 0.96, opacity: 0.6 }}
          animate={{ scale: 1, opacity: 1, ...m.animate }}
          transition={{ ...m.transition, scale: { duration: 0.25 }, opacity: { duration: 0.25 } }} />
      </div>
    </div>
  )
}
