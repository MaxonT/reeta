import { motion } from 'framer-motion'

// Small shared pieces of the loop chrome.

export function Flame({ lit = true, size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className={`lp-flame ${lit ? 'is-lit' : ''}`}>
      <path d="M12.6 2.2c.3 2.6-1 4.3-2.4 5.9C8.7 9.8 7 11.6 7 14.6A5 5 0 0 0 12 20a5 5 0 0 0 5-5.2c0-1.7-.7-3-1.5-4 .1 1.2-.4 2.3-1.4 2.7.6-3.6-.6-8.2-1.5-11.3Z" fill="currentColor" />
      <path d="M12 20a3 3 0 0 1-3-3.1c0-1.6 1.2-2.6 2.1-3.6.2 1 .9 1.7 1.7 1.9-.1-.8.2-1.5.7-2 .9 1 1.5 2.2 1.5 3.6A3 3 0 0 1 12 20Z" fill="#fff" opacity=".55" />
    </svg>
  )
}

export function Streak({ count = 0, bump = false }) {
  return (
    <div className={`lp-chip lp-streak ${count > 0 ? 'is-on' : ''}`} aria-label={`${count} day streak`} title={`${count} day streak`}>
      <Flame lit={count > 0} />
      <motion.span key={count} initial={bump ? { scale: 1.8, opacity: 0 } : false} animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 380, damping: 16 }}>{count}</motion.span>
    </div>
  )
}

export function Level({ name }) {
  return (
    <div className="lp-chip lp-level" title="Reeta's level">
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 1.5 8.5 12 14l8.5-4.45V16H22V8.5L12 3Zm-6 9.6v3.6c0 1.6 2.7 3.3 6 3.3s6-1.7 6-3.3v-3.6l-6 3.1-6-3.1Z" fill="currentColor" /></svg>
      <span>{name || 'Freshman'}</span>
    </div>
  )
}

export function TopBar({ onClose, title, children }) {
  return (
    <div className="lp-top">
      {onClose
        ? <button className="lp-icon-btn" onClick={onClose} aria-label="Back to home">
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" /></svg>
          </button>
        : <div className="lp-brand">Reeta</div>}
      {title && <div className="lp-top-title">{title}</div>}
      <div className="lp-top-right">{children}</div>
    </div>
  )
}

// Dots for the 5 concepts. Filled = mastered.
export function Progress({ mastered = 0, total = 5, concepts }) {
  const dots = concepts?.length ? concepts : Array.from({ length: total }, (_, i) => ({ id: i, status: i < mastered ? 'correct' : 'missing' }))
  return (
    <div className="lp-progress" role="img" aria-label={`${mastered} of ${total} concepts mastered`}>
      <div className="lp-dots">
        {dots.map((c) => <span key={c.id} className={`lp-dot ${c.status === 'correct' ? 'is-done' : ''}`} title={c.label} />)}
      </div>
      <span className="lp-progress-label">{mastered}/{total} mastered</span>
    </div>
  )
}
