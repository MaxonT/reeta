import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { isMuted, onMutedChange, play, setMuted } from '../lib/sfx.js'

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

export function MuteButton() {
  const [muted, setM] = useState(isMuted)
  useEffect(() => onMutedChange(setM), [])
  return (
    <button className={`lp-icon-btn lp-mute ${muted ? 'is-muted' : ''}`} aria-pressed={muted}
      aria-label={muted ? 'Turn sound on' : 'Turn sound off'} title={muted ? 'Sound off' : 'Sound on'}
      onClick={() => { setMuted(!muted); if (muted) play('sent') }}>
      <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5H4Z" fill="currentColor" />
        {muted
          ? <path d="m16 9.5 5 5m0-5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          : <path d="M15.5 9a4 4 0 0 1 0 6m2.2-8.4a7 7 0 0 1 0 10.8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />}
      </svg>
    </button>
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
      <div className="lp-top-right">{children}<MuteButton /></div>
    </div>
  )
}
