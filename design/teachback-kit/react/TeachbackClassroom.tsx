import React, { useRef, useState } from 'react';
import './teachback.css';

export type Phase = 'ready' | 'recording' | 'transcribing' | 'testing' | 'review' | 'error';
export type Sentence = { id: string; text: string; timestamp: string; attempt: number };
export type Note = { id: string; text: string; sentenceIds: string[]; draft?: string; margin?: string };
export type Question = {
  id: string; prompt: string; studentAnswer: string; correctAnswer: string;
  correct: boolean; noteIds: string[]; sentenceIds: string[]; feedback: string;
};
export type ClassroomProps = {
  phase: Phase; topic: string; code: string; sentences: Sentence[]; notes: Note[];
  questions: Question[];
  /** Supply only the result returned by the server. Never infer a pass from animation. */
  passed?: boolean;
  /** True only after the current notebook has finished processing. */
  notebookReady: boolean;
  recordingTime?: string; errorMessage?: string;
  assetBase?: string;
  onStartLecture: () => void; onStopLecture: () => void;
  onTakeExam: () => void; onReteach: () => void; onRetry: () => void;
};

export function StudentAvatar({ expression, assetBase = '/teachback' }: {
  expression: 'listening' | 'thinking' | 'confused' | 'proud'; assetBase?: string;
}) {
  return <img className="tb-student" src={`${assetBase}/student-${expression}.svg`}
    alt={`AI student: ${expression}`} width="120" height="120" />;
}

export default function TeachbackClassroom(props: ClassroomProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const evidenceRegion = useRef<HTMLDivElement>(null);
  const selected = props.questions.find(q => q.id === selectedId);
  const noteIds = new Set(selected?.noteIds ?? []);
  const sentenceIds = new Set([
    ...(selected?.sentenceIds ?? []),
    ...props.notes.filter(n => noteIds.has(n.id)).flatMap(n => n.sentenceIds),
  ]);
  const hasSource = props.sentences.some(s => sentenceIds.has(s.id));
  const busy = props.phase === 'transcribing' || props.phase === 'testing';
  const expression = props.phase === 'recording' ? 'listening' : busy ? 'thinking'
    : props.phase === 'review' && props.passed === true ? 'proud'
    : props.phase === 'review' && selected && !selected.correct ? 'confused' : 'listening';
  function trace(question: Question) {
    setSelectedId(question.id);
    evidenceRegion.current?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'start',
    });
  }
  return <div className="teachback">
    <header className="tb-header"><strong>Teachback.</strong><span>{props.topic}</span></header>
    <main>
      <div className="tb-controls" aria-label="Lecture controls">
        {props.phase === 'recording'
          ? <><span role="status">● Recording · {props.recordingTime ?? '00:00'}</span><button onClick={props.onStopLecture}>Stop lecture</button></>
          : <button onClick={props.onStartLecture} disabled={busy}>Start lecture</button>}
        <button className="tb-secondary" onClick={props.onTakeExam}
          disabled={!props.notebookReady || busy || props.phase === 'recording'}>Give exam</button>
        <span role="status">{props.phase === 'transcribing' ? 'Transcribing lecture…' : props.phase === 'testing' ? 'Taking the exam…' : ''}</span>
        {props.phase === 'error' && <div role="alert">{props.errorMessage ?? 'Something went wrong.'} <button onClick={props.onRetry}>Retry</button></div>}
      </div>
      <div className="tb-scene" ref={evidenceRegion}>
        <section className="tb-board" aria-label="Chalkboard">
          <small>Lesson / {props.topic}</small><h1>Every call needs a way home.</h1>
          <pre><code>{props.code}</code></pre>
          <h2>Your lecture</h2>
          {props.sentences.length === 0 && <p>Your spoken lecture will appear here.</p>}
          {props.sentences.map(s => <div key={s.id} className={`tb-sentence ${sentenceIds.has(s.id) ? 'tb-linked' : ''}`}>
            <small>{s.id} · {s.timestamp} · Attempt {s.attempt}</small><p>“{s.text}”</p>
            {sentenceIds.has(s.id) && <span className="tb-evidence-label">Source for {selected?.id}</span>}
          </div>)}
          <div className="tb-dust" aria-hidden="true" />
          <div className="tb-tray" aria-hidden="true"><span className="tb-chalk" /><span className="tb-eraser" /></div>
        </section>
        <section className="tb-notebook" aria-label="Student notebook">
          <small>Student notebook</small><h2>What you taught me</h2>
          {props.notes.length === 0 && <p>Waiting for your first lesson…</p>}
          {props.notes.map((n, i) => <article key={n.id} className={`tb-note ${noteIds.has(n.id) ? 'tb-linked' : ''}`}>
            {n.draft && <del>{n.draft}</del>}
            <p>{String(i + 1).padStart(2, '0')}. {n.text}</p>
            <small>{n.id} · {n.sentenceIds.length ? `Source: ${n.sentenceIds.join(', ')}` : 'Not covered in your lecture'}</small>
            {n.margin && <aside>↳ {n.margin}</aside>}
          </article>)}
          <div className="tb-scribble" aria-hidden="true" />
        </section>
      </div>
      <div className="tb-student-row"><StudentAvatar expression={expression} assetBase={props.assetBase} />
        <p>{expression === 'proud' ? 'I passed! Your lesson helped.' : expression === 'thinking' ? 'Working through what you taught me…' : expression === 'confused' ? 'Can we go over this part again?' : 'I’m ready to learn from you.'}</p>
      </div>
      <section className="tb-exam" aria-label="Exam review"><h2>Exam review</h2>
        {props.questions.length === 0 && <p>Finish your lecture, then give the exam.</p>}
        {props.questions.map(q => <article key={q.id} className={`tb-question ${selectedId === q.id ? 'tb-linked' : ''}`}>
          <span className={q.correct ? 'tb-correct' : 'tb-wrong'}>{q.correct ? '✓ Correct' : '× Incorrect'} · {q.id}</span>
          <h3>{q.prompt}</h3><p>Student answer: {q.studentAnswer}</p>
          {!q.correct && <><p>Correct answer: {q.correctAnswer}</p><p className="tb-pen">{q.feedback}</p>
            <button onClick={() => trace(q)} aria-pressed={selectedId === q.id}>Trace to your words</button></>}
        </article>)}
        <p role="status" aria-live="polite">{selected ? hasSource ? `${selected.id}: matching notes and original sentences are highlighted above.` : `${selected.id}: Not covered in your lecture.` : 'Select an incorrect answer to review its evidence.'}</p>
        {props.phase === 'review' && props.passed !== true && <button onClick={props.onReteach}>Re-teach this lesson</button>}
      </section>
    </main>
  </div>;
}
