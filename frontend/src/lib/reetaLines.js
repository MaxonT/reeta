// Reeta's built in lines. Personality: the earnest dummy. She tries hard, believes everything you
// say, repeats your mistakes back sincerely, is sad when you skip and proud when she passes.
// Keep lines short, warm, funny, never mean, and without dashes as punctuation.

export const lines = {
  home({ mood, streak = 0 }) {
    if (mood === 'proud') return 'We passed today!! I told my whole dorm you are my professor. One more lesson?'
    if (mood === 'sad') return 'You didn’t come yesterday. I studied alone and learned nothing 🥲 Teach me something?'
    if (mood === 'confused') return 'I did exactly what you told me and still got some wrong. Can you teach me again?'
    if (streak > 0) return `${streak} day streak! I have a quiz today and I only know what you tell me.`
    return 'I have a quiz today and I know nothing 😭 Can you teach me?'
  },
  teachIdle: 'Okay! I am ready. Explain it like I know nothing. Because I know nothing.',
  teachFix: 'I really thought I had this one. Can you say it again, slowly?',
  transcriptDone: 'Got it! I wrote down every word. Exactly how you said it.',
  answering: 'Hmm. What did my professor say about this…',
  graded: { correct: 'Yes! I remembered!', wrong: 'Wait… that’s what you told me?', not_taught: 'You never taught me this one 😶' },
  recording: 'Mhm. Mhm! Writing down every single word.',
  processing: 'Hold on, I am writing it all down…',
  quizStart: 'Okay. Deep breath. I only use what you taught me.',
  pass: "I GOT THEM ALL. You're the best professor ever.",
  fail: 'I did exactly what you told me... and still got it wrong? 🥲',
  notTaught: 'You never taught me this',
}
