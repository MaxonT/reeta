// Reeta's built in lines. Personality: the earnest dummy. She tries hard, believes everything you
// say, repeats your mistakes back sincerely, is sad when you skip and proud when she passes.
// Keep lines short, warm, funny, never mean, and without dashes as punctuation.


// Same mapping as the backend's level_for: Freshman 0 to 1 mastered, Sophomore 2, Junior 3 to 4, Graduate 5.
export function levelFor(mastered = 0, total = 5) {
  if (total && mastered >= total) return 'Graduate'
  if (mastered >= 3) return 'Junior'
  if (mastered === 2) return 'Sophomore'
  return 'Freshman'
}

// How Reeta talks about each concept in a sentence.
const NOUNS = {
  self_call: 'how a function can call itself',
  base_case: 'base cases',
  smaller_problem: 'what to pass into the next call',
  independent_frames: 'what happens to variables in each call',
  return_propagation: 'how return values come back up',
}
export function conceptNoun(conceptId, label) {
  return NOUNS[conceptId] || (label ? label.toLowerCase() : 'recursion')
}

export function shorten(text = '', max = 80) {
  const t = text.trim()
  return t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t
}

export const lines = {
  home({ mood, ask, quote }) {
    const noun = ask ? conceptNoun(ask.concept_id, ask.label) : null
    if (mood === 'proud') return 'We passed today!! I told my whole dorm you are my professor. One more lesson?'
    if (mood === 'sad') return `You didn't come yesterday. I studied alone and learned nothing 🥲 Can we do ${noun || 'recursion'}?`
    if (!ask) return 'I know all five things now. I feel like a genius. Teach me anything, I will believe you.'
    if (ask.reason === 'misconception' && quote) return `You told me “${shorten(quote, 70)}” and I believe it with my whole heart. Can you teach me ${noun} again, just in case?`
    return `I have a quiz tomorrow and I still don't get ${noun} 😭 can you teach me?`
  },
  teachIdle: 'Okay! I am ready. Explain it like I know nothing. Because I know nothing.',
  teachFix: (label, conceptId) => `I really thought I had ${conceptNoun(conceptId, label)}. Can you say it again, slowly?`,
  recording: 'Mhm. Mhm! Writing down every single word.',
  processing: 'Hold on, I am writing it all down…',
  notesDone: 'Got it! I wrote everything down. Exactly how you said it.',
  notesEmpty: 'I wrote… nothing? I don’t think that was about recursion. Try again?',
  quizStart: 'Okay. Deep breath. I only use what you taught me.',
  quizThinking: ['Hmm. What would my professor say…', 'I remember this part!', 'Okay, last one. I can do this.'],
  pass: "I GOT THEM ALL. You're the best professor ever.",
  fail: 'I did exactly what you told me... and still got it wrong? 🥲',
  notTaught: 'You never taught me this',
  doneForToday: 'See you tomorrow, professor! I will be right here. Studying. Probably wrong.',
}
