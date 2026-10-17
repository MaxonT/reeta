import { motion, useReducedMotion } from 'framer-motion'

// Character art by Semi (design/teachback-kit). expression: listening | confused | thinking | happy
// The four SVGs live in public/teachback/. "happy" is drawn with the proud face.
const FACES = { listening: 'listening', thinking: 'thinking', confused: 'confused', happy: 'proud' }
const BASE = `${import.meta.env.BASE_URL}teachback/`

// Motion follows the kit: idle listening is still, a 2px pencil bob while thinking,
// a short brow tilt when confused, one 300ms bounce when proud. Off under reduced motion.
const MOTION = {
  listening: { animate: {}, transition: {} },
  thinking: { animate: { y: [0, -2, 0] }, transition: { duration: 1.2, repeat: Infinity } },
  confused: { animate: { rotate: [0, -3, 0] }, transition: { duration: 0.4 } },
  proud: { animate: { y: [0, -8, 0] }, transition: { duration: 0.3 } },
}

export default function AIStudent({ expression = 'listening', raisedHand = false, size = 180, say }) {
  const face = FACES[expression] || FACES.listening
  const reduce = useReducedMotion()
  const m = reduce ? MOTION.listening : MOTION[face]
  return (
    <div className={`student face-${face}`}>
      {say && (
        <motion.div className="bubble" key={say} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
          {say}
        </motion.div>
      )}
      <div className="avatar" style={{ width: size }}>
        <motion.img key={face} src={`${BASE}student-${face}.svg`} alt={`AI student: ${face}`}
          width={size} height={size} animate={m.animate} transition={m.transition} />
        {raisedHand && <span className="hand-up" aria-hidden="true">✋</span>}
      </div>
    </div>
  )
}

export function moodFromNotebook(concepts = []) {
  if (concepts.some((c) => c.status === 'misconception')) return 'confused'
  if (concepts.length && concepts.every((c) => c.status === 'correct')) return 'happy'
  return 'listening'
}
