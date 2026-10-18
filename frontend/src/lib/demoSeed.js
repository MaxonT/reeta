// Demo prep, opened with http://localhost:5173/#demo: a clean session (no lectures, no uploaded notes,
// so the exam uses the default Python recursion notes) and a fresh local streak.
// With LLM_PROVIDER=mock the 3 questions are self call, base case and smaller problem, so the demo
// lesson in frontend/README.md scores 2/3 and one Fix it passes 3/3.
import { api } from './api.js'
import { clearLoopState } from './loopState.js'

export async function seedDemo() {
  clearLoopState()
  await api.reset()
}
