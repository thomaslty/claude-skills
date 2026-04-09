---
description: Commit staged/unstaged changes without the Co-Authored-By trailer
allowed-tools: Bash(git:*), Read, Glob, Grep
---

Create a git commit for the current changes. Do NOT append any "Co-Authored-By" trailer to the commit message.

## Steps

1. Run these in parallel to understand the current state:
   - `git status` (never use -uall flag)
   - `git diff` and `git diff --staged` to see all changes
   - `git log --oneline -10` to see recent commit style

2. Analyze all staged and unstaged changes. Draft a concise commit message that:
   - Follows the repository's existing commit message style (from git log)
   - Summarizes the "why" not the "what"
   - Is 1-2 sentences
   - Does NOT include any "Co-Authored-By" line — this is the whole point of this command

3. Stage relevant files by name (prefer specific files over `git add -A`). Do not stage files that look like secrets (.env, credentials, etc.).

4. Create the commit using a HEREDOC:
   ```
   git commit -m "$(cat <<'EOF'
   Your commit message here.
   EOF
   )"
   ```

5. Run `git status` after the commit to confirm success.

6. If a pre-commit hook fails, fix the issue and create a NEW commit (never amend).

## Important

- Never use `--no-verify` or `--no-gpg-sign`
- Never amend an existing commit unless the user explicitly asked
- Never push unless the user explicitly asked
- If there are no changes to commit, say so — do not create an empty commit
