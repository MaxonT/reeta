import { useMemo } from 'react'
import Reeta from './Reeta.jsx'
import { Streak, TopBar } from './ui.jsx'
import { lines } from '../lib/reetaLines.js'

// Home: Reeta asks to be taught. One big button, plus the course notes her quiz is written from.
export default function Home({ today, sources, onTeach, onNotes }) {
  const loading = sources === null
  const hello = useMemo(() => lines.home(today), [today.mood, today.streak])
  const notes = !sources?.length ? 'Python recursion (default)'
    : sources.length === 1 ? sources[0].filename : `${sources.length} files`
  return (
    <>
      <TopBar>
        <Streak count={today.streak} />
      </TopBar>

      <div className="lp-body lp-home">
        <Reeta mood={loading ? 'thinking' : today.mood} size={232}
          say={loading ? 'Finding my notebook…' : hello} idle />
        {today.last && (
          <p className="lp-last">Last quiz <b>{today.last.score}/{today.last.total}</b>{today.last.passed ? ' · passed' : ''}</p>
        )}
      </div>

      <div className="lp-actions">
        <button className="lp-notes-chip" onClick={onNotes} disabled={loading}>
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6V3Zm8 0v4h4M9 12h6M9 16h6" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinejoin="round" /></svg>
          <span className="lp-notes-chip-text">Course notes: <b>{notes}</b></span>
          <span className="lp-notes-chip-go" aria-hidden="true">Change</span>
        </button>
        <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={onTeach} disabled={loading}>Teach Reeta</button>
      </div>
    </>
  )
}
