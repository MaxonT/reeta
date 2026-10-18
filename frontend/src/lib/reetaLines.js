// Reeta's built in lines. Personality: the earnest, cheerful dummy. She tries hard, believes everything
// you say, encourages you, and never blames you: a wrong answer is "let's go over it". She speaks to you as "you", never "Professor".
// Keep lines short, warm, funny, never mean, and without dashes as punctuation.

// A random variant, never the same one twice in a row for the same list.
const last = new WeakMap()
export function pick(list) {
  if (list.length === 1) return list[0]
  let i
  do { i = Math.floor(Math.random() * list.length) } while (i === last.get(list))
  last.set(list, i)
  return list[i]
}

const RECORDING = [
  'Mhm. Go on, I’m writing it all down.',
  'Okay, I’m following. Keep going.',
  'I’m listening 👂',
  'Got it so far. Keep going!',
]
const PROCESSING = [
  'One sec, I’m writing that down…',
  'Okay, copying it into my notes…',
]
// After a lesson is saved: acknowledge what the person just did.
const TAUGHT = [
  'Okay, I wrote that down. Nice explanation!',
  'Thanks, that helps. It’s all in my notes now 📝',
  'Good one. I’ve got everything you said.',
  'That was clear. Ready when you are!',
]
const TAUGHT_FIX = [
  'That helps, thank you for going over it again 💛',
  'Okay, that’s clearer now. I’ve got it written down.',
  'Thanks for sticking with me. Noted!',
]
const CORRECT = [
  'Yes! You taught me that 🎉',
  'I got it, because you explained it.',
  'That one was in my notes. Thanks to you!',
  'Right! That’s what you told me.',
]
const WRONG = [
  'Not quite. Want to go over that one again? 💪',
  'I got that one wrong. We can fix it.',
  'Hmm, I mixed it up. One more try and we’ll have it.',
]
const NOT_TAUGHT = [
  'You haven’t taught me this one yet. Want to? 🙋',
  'That one isn’t in my notes yet. Teach me?',
]

export const lines = {
  home({ mood, streak = 0 }) {
    if (mood === 'proud') return pick(['We passed today! That was all you 🎓 Another lesson?', 'We did it today! Want to keep going?'])
    if (mood === 'sad') return 'Hey, I missed you! Ready to teach me something? 🥲'
    if (mood === 'confused') return 'Last time was tricky, but we can get it. Teach me again?'
    if (streak > 0) return `${streak} day streak! 🔥 I have a quiz today and I only know what you teach me.`
    return 'What are we trying to learn today?'
  },
  teachIdle: 'Okay, I’m ready! Explain it like I know nothing. Because I know nothing 😄',
  teachFix: 'I want to get this one right. Can you explain it again, nice and slow?',
  get recording() { return pick(RECORDING) },
  get processing() { return pick(PROCESSING) },
  get transcriptDone() { return pick(TAUGHT) },
  get transcriptFixDone() { return pick(TAUGHT_FIX) },
  answering: 'Hmm, what did you tell me about this…',
  quizStart: 'Okay, deep breath. I only know what you taught me.',
  graded: {
    get correct() { return pick(CORRECT) },
    get wrong() { return pick(WRONG) },
    get not_taught() { return pick(NOT_TAUGHT) },
  },
  // End of the quiz, by score.
  finished({ passed, score, total }) {
    if (passed && score === total) return 'Done! I think I got them all!'
    if (passed) return 'Done! I think I did it!'
    if (score > 0) return 'Done! Some went well and some were tricky.'
    return 'Done! That was tough, but now we know what to work on.'
  },
  pass({ score, total }) {
    if (score === total) return 'I got them all! Thanks to you 🏆'
    return 'I passed! You taught me well 🎉'
  },
  fail({ score }) {
    if (score > 0) return 'So close! You already taught me a lot. A little more and we’ve got it 💪'
    return 'That one was hard, but we can fix it together 💛'
  },
  notTaught: 'You haven’t taught me this one yet',
}
