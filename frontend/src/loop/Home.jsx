import Reeta from './Reeta.jsx'
import { Level, Progress, Streak, TopBar } from './ui.jsx'

// Home: Reeta asks to be taught. One big button.
export default function Home({ today, onTeach, onClassroom }) {
  const loading = !today
  return (
    <>
      <TopBar>
        <Streak count={today?.streak || 0} />
        <Level name={today?.level} />
      </TopBar>

      <div className="lp-body lp-home">
        <Reeta mood={loading ? 'thinking' : today.mood} size={232}
          say={loading ? 'Finding my notebook…' : today.line} idle />
        {today && <Progress mastered={today.progress.mastered} total={today.progress.total} concepts={today.concepts} />}
      </div>

      <div className="lp-actions">
        {today?.ask && <p className="lp-hint">Today: <b>{today.ask.label}</b> · about 60 seconds</p>}
        <button className="lp-btn lp-btn-primary lp-btn-xl" onClick={onTeach} disabled={loading}>Teach Reeta</button>
        <button className="lp-link" onClick={onClassroom}>Classroom view</button>
      </div>
    </>
  )
}
