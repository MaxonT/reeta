# How we work (HackTN26, 6 hours)

Goal: `main` always runs end to end, and nobody loses time to merge conflicts.

## 1. Who owns what

Repo lead: **MaxonT** (Tiger). Merges questions, branch protection, the `demo-ready` tag.

Most conflicts come from two people editing the same file. Stay in your lane, and say so in chat before touching someone else's.

| Area | Files | Owner |
|------|-------|-------|
| Backend logic | `backend/app/service.py`, `grading.py`, `main.py`, `backend/tests/` | **bowale-os** (Daniel) |
| Frontend scenes and design | `frontend/src/scenes/*`, `frontend/src/components/*`, `frontend/src/styles.css` | **O-Senbore** (Semi) |
| Content | `content/answer_key.json`, `content/exam.json` (Daniel S. adds concept edges here, coordinate) | **D4nI3l-oa** |
| OCI / Oracle | `backend/app/speech/oci_speech.py`, `llm/oci_genai.py`, `repo/oracle_repo.py` | **gogbonna** (Godswill) |
| Searchable knowledge graph | `GET /notebook/search` route + service method, concept edges in `content/answer_key.json`, edges in `frontend/src/components/ConceptMap.jsx` (coordinate with Semi) | **bowale-os** (Daniel) |

Shared hot files: `frontend/src/App.jsx`, `frontend/src/styles.css`, `backend/app/main.py`, `README.md`.
Post "editing App.jsx" in chat first, keep the change small, merge fast. Prefer new code in a new file.

## 2. Branch, PR, merge

1. Start every task from a fresh main:
   ```bash
   git checkout main && git pull
   git checkout -b <yourname>/<topic>      # e.g. tiger/office-hours-ui
   ```
2. One task per branch. A branch should live **under 1 hour**. Small PRs merge cleanly; big ones conflict.
3. Commit often. Before opening the PR, catch up with main and check it still works:
   ```bash
   git fetch origin
   git rebase origin/main                  # fix conflicts here, on your branch, never on main
   cd backend && pytest -q && cd ..
   cd frontend && npm run build && cd ..
   git push -u origin <yourname>/<topic>   # after a rebase: git push --force-with-lease
   ```
4. Open a PR into `main`. Title says what changed.
5. **Squash and merge**, then delete the branch. If tests and build pass, you can merge your own PR; ping the area owner if you touched their files.
6. After any merge, everyone runs `git checkout main && git pull` before starting the next task.

## 3. Never

1. Never push directly to `main`. Never `git push --force` to `main`.
2. Never rebase or force push a branch someone else is working on.
3. Never commit `.env`, API keys, OCI configs or wallets. Only `.env.example`.
4. Never rename concept or misconception ids in `content/*.json` without updating `exam.json` and telling the backend owner.
5. Never merge a PR with red tests or a broken `npm run build`.

## 4. Lockfiles and generated files

1. Adding a npm or pip dependency? Say it in chat. Only one person changes `package-lock.json` at a time.
2. If `package-lock.json` conflicts anyway, do not hand edit it:
   ```bash
   git checkout origin/main -- frontend/package-lock.json
   cd frontend && npm install && cd ..
   git add frontend/package-lock.json && git rebase --continue
   ```
3. `backend/data/` (SQLite DB, audio) is ignored. Never commit it.

## 5. Claude sessions

Claude (Claude Code) follows the same rules: it works on its own branch, rebases on `origin/main`, runs the tests and build, then opens a PR. It only pushes to `main` when a teammate explicitly asks it to.

## 6. Demo freeze

1. **Last 45 minutes before judging: bug fixes only**, no new features.
2. When the demo works, tag it so we can always go back:
   ```bash
   git tag demo-ready && git push origin demo-ready
   ```
3. If main breaks right before the demo: `git checkout demo-ready`.
