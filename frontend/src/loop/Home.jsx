import { useMemo } from 'react'
import Reeta from './Reeta.jsx'
import { Streak, TopBar } from './ui.jsx'
import { lines } from '../lib/reetaLines.js'

// Home: Reeta asks to be taught. One big button, plus the course notes her quiz is written from.
// account (logged in students only) adds a chip for their classes.
const STATUS = { not_started: 'not started', practicing: 'practicing', passed: 'passed' }

// Home: Reeta asks to be taught. One big button, plus what her quiz is written from: the topic a teacher set
// (logged in students) or the course notes (free practice).
export default function Home({ today, sources, onTeach, onNotes, account, classes, onClasses, onSignIn, topic, topics, onTopics }) {
  const loading = sources === null
  const hello = useMemo(() => lines.home(today), [today.mood, today.streak])
  const notes = !sources?.length ? 'Python recursion (default)'
    : sources.length === 1 ? sources[0].filename : `${sources.length} files`
  const inClass = account && classes?.length > 0
  const p = topic?.progress
  return (
    <>
      <TopBar>
        <Streak count={today.streak} />
        {account && (
          <button className="lp-icon-btn" onClick={onClasses} aria-label="My classes and account" title="My classes">
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M4.5 20c1.2-3.6 4-5.5 7.5-5.5s6.3 1.9 7.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          </button>
        )}
      </TopBar>

      <div className="lp-body lp-home">
        <Reeta mood={loading ? 'thinking' : today.mood} size={232}
          say={loading ? 'Finding my notebook…' : topic ? `Teach me ${topic.title}!` : hello} idle />
        {topic && !topic.notes_count && (
          <p className="lp-hint">Your teacher hasn’t added notes for this topic yet, so Reeta can’t take a quiz on it.</p>
        )}
        {topic ? (
          <p className="lp-last">
            {p.quizzes ? <>Best <b>{p.best_percent}%</b> · {STATUS[p.status]}</> : <>{topic.class_name} · {STATUS[p.status]}</>}
          </p>
        ) : today.last && (
          <p className="lp-last">Last quiz <b>{today.last.score}/{today.last.total}</b>{today.last.passed ? ' · passed' : ''}</p>
        )}
      </div>

      <div className="lp-actions">
        {account && !inClass && (
          <button className="lp-notes-chip" onClick={onClasses}>
            <ClassIcon />
            <span className="lp-notes-chip-text">{classes === null ? 'Loading classes…' : <b>Join your class</b>}</span>
            <span className="lp-notes-chip-go" aria-hidden="true">Join</span>
          </button>
        )}
        {inClass && (
          <button className="lp-notes-chip" onClick={onTopics}>
            <ClassIcon />
            <span className="lp-notes-chip-text">
              {topic ? <>Topic: <b>{topic.title}</b></>
                : topics?.length ? <>Free practice · <b>{topics.length} topic{topics.length === 1 ? '' : 's'} assigned</b></>
                : <>Free practice</>}
            </span>
            <span className="lp-notes-chip-go" aria-hidden="true">Change</span>
          </button>
        )}
        {!topic && (
          <button className="lp-notes-chip" onClick={onNotes} disabled={loading}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6V3Zm8 0v4h4M9 12h6M9 16h6" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinejoin="round" /></svg>
            <span className="lp-notes-chip-text">Course notes: <b>{notes}</b></span>
            <span className="lp-notes-chip-go" aria-hidden="true">Change</span>
          </button>
        )}
        <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={onTeach} disabled={loading}>Teach Reeta</button>
        {onSignIn && <button className="lp-link" onClick={onSignIn}>Log in or sign up to join a class</button>}
      </div>
    </>
  )
}

function ClassIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 9 12 4l9 5-9 5-9-5Zm4 2.5V16c0 1.4 2.2 3 5 3s5-1.6 5-3v-4.5" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinejoin="round" /></svg>
}
