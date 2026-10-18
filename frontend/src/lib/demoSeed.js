// Demo prep, opened with http://localhost:5173/#demo. Resets the session and quietly teaches Reeta the
// background (base case, smaller problem, return propagation) as one typed, confirmed lecture.
// Then the on stage lesson "A recursive function calls itself. All calls share the same variables."
// scores 2/3 (q6 wrong, with the Professor's sentence), and one Fix it on independent frames passes 3/3.
// Uses only the existing API; grading stays in backend/app/grading.py.
import { api } from './api.js'

export const DEMO_SEED = 'Recursion needs a base case where it stops, otherwise it recurses forever. '
  + 'Each call works on a smaller problem that moves toward the base case. '
  + 'The return value passes back up through each caller.'

export async function seedDemo() {
  await api.reset()
  const res = await api.postLecture({ kind: 'lecture', text: DEMO_SEED })
  const ids = res.proposed_entries.map((e) => e.id)
  if (ids.length) await api.confirm(res.lecture.id, { entry_ids: ids })
}
