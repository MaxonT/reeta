import { useState } from 'react'
import Classes from './Classes.jsx'
import ClassView from './ClassView.jsx'
import StudentGrades from './StudentGrades.jsx'
import '../loop/loop.css'
import '../auth/account.css'
import './teacher.css'

// Teacher dashboard: Classes -> a class (Gradebook | Topics) -> one student's grades. Grades only, never recordings.
export default function TeacherApp({ user, onLogout }) {
  const [view, setView] = useState({ name: 'classes' }) // | {name:'class', classId, tab} | {name:'student', classId, studentId}
  const toClasses = () => setView({ name: 'classes' })
  const toClass = (classId, tab = 'gradebook') => setView({ name: 'class', classId, tab })

  return (
    <div className="lp-app tc-app">
      <header className="tc-header">
        <button className="lp-brand tc-brand" onClick={toClasses}>Reeta</button>
        <span className="tc-role">Teacher</span>
        <div className="tc-header-right">
          <span className="tc-user">{user.name}</span>
          <button className="lp-btn lp-btn-secondary ac-small-btn" onClick={onLogout}>Log out</button>
        </div>
      </header>
      <main className="tc-shell">
        {view.name === 'classes' && <Classes onOpen={toClass} />}
        {view.name === 'class' && (
          <ClassView classId={view.classId} tab={view.tab} onTab={(tab) => toClass(view.classId, tab)} onBack={toClasses}
            onStudent={(studentId) => setView({ name: 'student', classId: view.classId, studentId })} />
        )}
        {view.name === 'student' && (
          <StudentGrades classId={view.classId} studentId={view.studentId} onBack={() => toClass(view.classId)} />
        )}
      </main>
    </div>
  )
}
