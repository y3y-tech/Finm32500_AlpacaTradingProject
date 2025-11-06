---
description: Convert TODO.md tasks to GitHub issues with labels
---

Parse the TODO.md file and create GitHub issues for all unchecked tasks. This command will:

1. Parse TODO.md to extract tasks with their priority (P0-P4), ownership (AI/Human/Collab), and descriptions
2. Create GitHub issues for any tasks that don't already have issue references
3. Apply appropriate labels for priority, theme, and ownership
4. Update TODO.md with issue references (e.g., [#123])

**Prerequisites:**
- GitHub CLI (`gh`) must be installed and authenticated
- Labels should already exist (use `/create-labels` first if needed)

**What it does:**
- Skips tasks that already have `[#NUM]` references
- Intelligently matches task titles to determine themes (strategy, testing, risk-management, etc.)
- Preserves all formatting and content in TODO.md
- Provides a summary of created issues

Run this command when you've added new tasks to TODO.md and want to track them as GitHub issues.
