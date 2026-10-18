import React from 'react';
import TeachbackClassroom, { type ClassroomProps } from './TeachbackClassroom';

/** Visual fixture only. Replace these values with your application state. */
const example: ClassroomProps = {
  phase: 'review', topic: 'Python recursion', notebookReady: true, passed: false,
  code: 'def countdown(n):\n    print(n)\n    countdown(n - 1)',
  sentences: [{id:'S03', text:'A recursive function keeps calling itself.', timestamp:'00:18', attempt:1}],
  notes: [{id:'N02', text:'Keep calling the function.', sentenceIds:['S03'],
    draft:'Repeat forever?', margin:'Ask professor: when does it stop?'}],
  questions: [{id:'Q03', prompt:'Does every recursive function terminate?',
    studentAnswer:'Yes', correctAnswer:'No', correct:false, noteIds:['N02'], sentenceIds:['S03'],
    feedback:'Missing: a reachable base case and progress toward it.'}],
  onStartLecture:()=>console.info('Connect the recording start handler here.'),
  onStopLecture:()=>console.info('Stop recording and send audio to your transcription pipeline.'),
  onTakeExam:()=>console.info('Call your deterministic grading endpoint here.'),
  onReteach:()=>console.info('Start a new lecture attempt; preserve the original transcript.'),
  onRetry:()=>console.info('Retry the failed operation using retained input.'),
};
export default function Example() { return <TeachbackClassroom {...example} />; }
