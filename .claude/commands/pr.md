Review the current branch diff and open a pull request.

Works in any of the three repos: monorepo root, agriTwin-app, or agriTwin-etl.
If $ARGUMENTS is provided, treat it as an instruction to the review (e.g. "focus on security" or "skip review").

## Step 1 — Identify the working repo

Determine which repo has the active feature branch:
- Run `git branch --show-current` in the monorepo root
- Run `git -C agriTwin-app branch --show-current`
- Run `git -C agriTwin-etl branch --show-current`

The repo whose current branch is NOT main/master is the one with the changes.
If more than one repo has a feature branch, handle each one in sequence.

## Step 2 — Collect the diff

In the identified repo, run:
- `git log --oneline main..HEAD` (or `master..HEAD` for the monorepo root) — commits to be PRed
- `git diff main..HEAD` (or `master..HEAD`) — full diff

If the branch has no commits ahead of main/master, stop and tell the user there is nothing to PR.

## Step 3 — Code review

Read the full diff and review it for:
- **Correctness bugs** — logic errors, off-by-ones, wrong conditions
- **Security issues** — hardcoded secrets, SQL injection, XSS, unvalidated input
- **Obvious simplifications** — duplicated code, unnecessary complexity

Present findings as a short bulleted list (Critical / Warning / Suggestion).
If there are Critical or Warning items, ask the user whether to fix them before opening the PR or proceed anyway.
If $ARGUMENTS is "skip review", skip this step entirely.

## Step 4 — Ask for PR approval

Show:
- Target repo and branch → main (or master)
- Commits being merged (hash + message)
- Review verdict (clean / N issues found)

Then ask: **"Open this pull request? (yes / no)"**

Do not proceed until the user confirms.

## Step 5 — Create the PR

In the identified repo directory, run:

```
gh pr create \
  --title "<imperative-mood title, max 60 chars>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullet points describing what changed and why>

## Test plan
<bullet checklist of what to verify before merging>

🤖 Generated with [Claude Code](https://claude.ai/code)
EOF
)"
```

Derive the title and body from the commit messages and diff — do not use generic placeholders.

## Step 6 — Report

Print the PR URL returned by `gh pr create`.
Remind the user: **review and merge on GitHub, then run `/deploy`.**
