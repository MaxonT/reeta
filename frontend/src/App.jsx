import { useEffect, useState } from 'react'
import Loop from './loop/Loop.jsx'
import ClassroomApp from './ClassroomApp.jsx'

// Default: the daily loop (Home, Teach, Quiz, Result). The old six scenes live at #classroom.
const viewFromHash = () => (window.location.hash === '#classroom' ? 'classroom' : 'loop')

export default function App() {
  const [view, setView] = useState(viewFromHash)
  useEffect(() => {
    const onHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const go = (v) => { window.location.hash = v === 'classroom' ? 'classroom' : ''; setView(v) }
  return view === 'classroom'
    ? <ClassroomApp onExit={() => go('loop')} />
    : <Loop onClassroom={() => go('classroom')} />
}
