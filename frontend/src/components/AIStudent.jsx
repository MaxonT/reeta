import { motion } from 'framer-motion'

// Original simple character. expression: listening | confused | thinking | happy
const FACES = {
  listening: { brows: ['M58 70 q8 -5 16 0', 'M86 70 q8 -5 16 0'], eyes: 'open', mouth: 'M70 104 q10 6 20 0' },
  confused: { brows: ['M58 66 q8 4 16 2', 'M86 70 q8 -8 16 -4'], eyes: 'open', mouth: 'M70 106 q5 -5 10 0 q5 5 10 0' },
  thinking: { brows: ['M58 68 q8 -3 16 0', 'M86 64 q8 -3 16 0'], eyes: 'up', mouth: 'M74 105 h12' },
  happy: { brows: ['M58 66 q8 -7 16 0', 'M86 66 q8 -7 16 0'], eyes: 'closed', mouth: 'M66 100 q14 16 28 0 z' },
}

export default function AIStudent({ expression = 'listening', raisedHand = false, size = 180, say }) {
  const f = FACES[expression] || FACES.listening
  const bob = expression === 'happy' ? { y: [0, -8, 0] } : expression === 'thinking' ? { rotate: [0, -4, 0] } : { y: [0, -2, 0] }
  return (
    <div className="student" style={{ width: size }}>
      {say && (
        <motion.div className="bubble" key={say} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}>
          {say}
        </motion.div>
      )}
      <motion.svg viewBox="0 0 160 200" width={size} height={size * 1.25}
        animate={bob} transition={{ duration: expression === 'happy' ? 0.6 : 2.4, repeat: Infinity }}>
        {/* raised hand */}
        {raisedHand && (
          <motion.g initial={{ rotate: 30 }} animate={{ rotate: [0, -6, 0] }} transition={{ duration: 0.8, repeat: Infinity }}
            style={{ originX: '120px', originY: '150px' }}>
            <path d="M118 150 L136 60" stroke="#e76f51" strokeWidth="16" strokeLinecap="round" />
            <circle cx="137" cy="52" r="11" fill="#ffd8b1" stroke="#5a3e2b" strokeWidth="2" />
          </motion.g>
        )}
        {/* body */}
        <path d="M30 196 q0 -60 50 -62 q50 2 50 62 z" fill="#e76f51" stroke="#5a3e2b" strokeWidth="3" />
        <path d="M66 136 l14 16 l14 -16" fill="none" stroke="#5a3e2b" strokeWidth="3" />
        {/* head */}
        <circle cx="80" cy="84" r="46" fill="#ffd8b1" stroke="#5a3e2b" strokeWidth="3" />
        <path d="M36 76 q4 -44 46 -42 q40 0 42 40 q-14 -18 -30 -16 q-6 -12 -22 -6 q-18 -8 -36 24 z" fill="#3d2c22" />
        {/* cheeks */}
        <circle cx="56" cy="98" r="6" fill="#f4a3a3" opacity="0.6" />
        <circle cx="104" cy="98" r="6" fill="#f4a3a3" opacity="0.6" />
        {/* brows */}
        {f.brows.map((d, i) => <path key={i} d={d} fill="none" stroke="#3d2c22" strokeWidth="3" strokeLinecap="round" />)}
        {/* eyes */}
        {f.eyes === 'closed' ? (
          <>
            <path d="M60 84 q6 -6 12 0" fill="none" stroke="#3d2c22" strokeWidth="3" strokeLinecap="round" />
            <path d="M88 84 q6 -6 12 0" fill="none" stroke="#3d2c22" strokeWidth="3" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="66" cy="84" r="5" fill="#3d2c22" />
            <circle cx="94" cy="84" r="5" fill="#3d2c22" />
            <circle cx={f.eyes === 'up' ? 68 : 67} cy={f.eyes === 'up' ? 81 : 83} r="1.6" fill="#fff" />
            <circle cx={f.eyes === 'up' ? 96 : 95} cy={f.eyes === 'up' ? 81 : 83} r="1.6" fill="#fff" />
          </>
        )}
        {/* mouth */}
        <path d={f.mouth} fill={expression === 'happy' ? '#9b2226' : 'none'} stroke="#3d2c22" strokeWidth="3" strokeLinecap="round" />
        {/* thought marks */}
        {expression === 'confused' && <text x="122" y="40" className="mark">?</text>}
        {expression === 'thinking' && <text x="118" y="36" className="mark">…</text>}
        {expression === 'happy' && <text x="120" y="38" className="mark">★</text>}
      </motion.svg>
    </div>
  )
}

export function moodFromNotebook(concepts = []) {
  if (concepts.some((c) => c.status === 'misconception')) return 'confused'
  if (concepts.length && concepts.every((c) => c.status === 'correct')) return 'happy'
  return 'listening'
}
