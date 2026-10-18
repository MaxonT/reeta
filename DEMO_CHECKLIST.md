# Demo checklist: photosynthesis with the real models

The sequence that passed 3/3 on 2026-10-18. Use it before every demo and after any change to the prompts,
the exam code or `.env`. The recursion script with the offline mock is in `frontend/README.md`.

## 1. Before you start

- [ ] `.env`: `LLM_PROVIDER=oci`, `DB_PROVIDER=oracle`, `OPENAI_API_KEY` set (OCI fails over to OpenAI, then the mock).
- [ ] `QUESTION_SOURCE=llm` (questions from your notes) or `fixed` (the three easy questions in
      `content/photosynthesis_questions.json`, always in the same order unless `QUESTION_SHUFFLE=true`).
- [ ] `cd backend && .venv/Scripts/python.exe -m pytest -q` passes.
- [ ] Start the backend, then `http://localhost:8000/health` shows `"llm":"oci"` and `"db":"oracle"`.
- [ ] Start the frontend (`npm run dev` in `frontend/`).
- [ ] Open `http://localhost:5173/#demo` to reset the session (lectures, notes, attempts, streak).
- [ ] Watch the backend terminal during the run. Any line starting `[llm] primary ... failed, using fallback` means
      OCI (or OpenAI) failed and a weaker model answered.

## 2. The run

1. **Notes** (Home, "Course notes", Change): upload `content/photosynthesis.txt`. Skip this if you use `fixed`.
   `#demo` clears uploaded notes, so redo it after every reset.
2. **Teach**: record, or paste as typed text, an accurate lecture on photosynthesis (reading `photosynthesis.txt`
   aloud works). Record it as a normal lecture, not as office hours.
3. **Quiz**: Reeta answers 3 questions. Expect most to be correct. A question the lecture did not cover should
   show "never taught", with a plain "I don't know" and no extra remarks.
4. **Fix it / Fix all N** (only if questions failed): Reeta goes through every question she got wrong, one at a
   time ("Fix 1 of 3"). Record a short, accurate follow-up for each, then press "Next question". Each recording is
   saved as office hours and added to your lecture. After the last one the button says "Quiz Reeta".
5. **Quiz again**: expect the failed topics to pass. With `fixed` the quiz repeats the same three questions. With
   `llm` the model writes new ones, so a topic you re-taught might not come up. Result screen: confetti and the
   streak at 1.

To demo a wrong-answer failure on purpose, teach one wrong fact, for example "the oxygen comes from the carbon
dioxide". The matching question should be marked wrong ("Because you said ...") and not "never taught".

## 3. What correct looks like

- [ ] Every answer sentence is backed by a quote shown under it ("You taught me" / "Because you said").
- [ ] An answer built from several sentences shows several quotes, each with its own replay button ("And you said").
- [ ] A question the lecture never touched gets "I don't know", with no hedging text.
- [ ] Questions do not contain their own answer.
- [ ] With `fixed`, every run asks the same three questions in the same order: where the oxygen comes from, what
      happens as carbon dioxide rises, what happens on a hot, dry day. Teach those three topics.

## 4. If something looks wrong

| Symptom | Likely cause | Check |
|---|---|---|
| Every question says "never taught" | Reeta got an empty or wrong transcript | `GET /lectures` (header `X-Session-Id: demo`): is the newest `lecture` non-empty, with text? |
| Answers mix a wrong old lecture and the new one | Old lectures in the session | Only the newest `lecture` plus office hours after it count. Reset with `#demo` anyway. |
| "Reeta's quote is not in your lectures: ..." | She misquoted. The rejected text is in the feedback. | Rerun. If it repeats, check the quote against the lecture wording. |
| Answer looks right but marked "never taught" | A claim in her answer is in none of her quotes (strict judge) | Read the feedback line, and teach that fact as its own sentence. |
| Questions are bland or about "In your own words, explain: base case" | The mock wrote them, so OCI and OpenAI both failed | Look for `[llm] primary generate_questions failed` in the backend terminal. |
| Notes screen error on upload | Oracle connection | Backend log. A `DPY-4011` means a stale pooled connection; retry. |
| Old classroom screens error with "no longer supported" | Expected. Those endpoints return HTTP 410. | Use the loop UI at `/`. |

## 5. After the run

- [ ] Open `#demo` again to reset before the next run.
- [ ] Note any `[llm] ... using fallback` lines you saw and why.
