---
description: Sync TODO.md checkboxes with GitHub issue status
---

Synchronize the completion status between TODO.md and GitHub issues:

**What it does:**
1. Reads all issue references from TODO.md (e.g., `[#123]`)
2. Fetches the current status of each issue from GitHub (open/closed)
3. Updates checkboxes in TODO.md:
   - `- [ ]` for open issues
   - `- [x]` for closed issues
4. Reports any mismatches or issues not found

**Use cases:**
- After closing issues on GitHub, update TODO.md to reflect completion
- Get a quick overview of what's done vs. what's remaining
- Keep the local TODO.md file in sync with GitHub's source of truth

This is useful when team members close issues on GitHub and you want your local TODO.md to reflect the latest status.

**Note:** This is a one-way sync (GitHub → TODO.md). Manual checkbox changes in TODO.md won't affect GitHub issues.
