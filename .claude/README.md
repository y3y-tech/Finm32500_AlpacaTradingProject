# Claude Code Commands & Scripts

This directory contains custom slash commands and Python scripts for managing the Alpaca Trading Project.

## Directory Structure

```
.claude/
├── commands/          # Slash commands for Claude Code
│   ├── create-labels.md
│   ├── todo-to-issues.md
│   ├── sync-todo-issues.md
│   └── issue-stats.md
├── scripts/           # Python automation scripts
│   ├── create_issues.py
│   ├── add_labels.py
│   ├── add_ownership_labels.py
│   ├── link_issues_in_todo.py
│   ├── sync_todo_issues.py
│   └── issue_stats.py
└── README.md          # This file
```

## Available Slash Commands

### `/create-labels`
Creates the standard set of GitHub labels for the project.

**Labels created:**
- Priority: P0-critical, P1-high, P2-medium, P3-low, P4-reach
- Ownership: better-for-ai, better-for-human, collaborative
- Themes: strategy, testing, risk-management, monitoring, infrastructure, analytics, code-quality, documentation

**Usage:** Run once at project setup or to reset labels.

### `/todo-to-issues`
Converts unchecked tasks in TODO.md to GitHub issues.

**What it does:**
- Parses TODO.md for tasks without issue references
- Creates GitHub issues with proper labels
- Updates TODO.md with issue references (e.g., [#123])
- Intelligently assigns theme labels based on content

**Usage:** Run when you've added new tasks to TODO.md.

### `/sync-todo-issues`
Syncs TODO.md checkboxes with GitHub issue status.

**What it does:**
- Checks status of all issues referenced in TODO.md
- Updates checkboxes to match GitHub (closed → checked, open → unchecked)
- Reports any issues not found

**Usage:** Run after closing issues on GitHub to update local TODO.md.

### `/issue-stats`
Displays comprehensive statistics about GitHub issues.

**Shows:**
- Total open/closed counts with completion percentages
- Breakdown by priority with progress bars
- Breakdown by ownership (AI/Human/Collaborative)
- Breakdown by theme
- List of critical P0 issues
- List of AI-ready issues

**Usage:** Run anytime for a project status overview.

## Using Slash Commands

In Claude Code, simply type the command:

```
/issue-stats
```

Claude will execute the command and show you the results.

## Running Scripts Directly

You can also run the Python scripts directly:

```bash
# Show issue statistics
python .claude/scripts/issue_stats.py

# Sync TODO.md with GitHub
python .claude/scripts/sync_todo_issues.py

# Create all issues from TODO.md
python .claude/scripts/create_issues.py
```

## Prerequisites

All scripts require:
- Python 3.7+
- GitHub CLI (`gh`) installed and authenticated
- Run from project root directory

## Label System

### Priority Labels
- **P0-critical** (red): Must complete before competition
- **P1-high** (orange): Should complete, high impact
- **P2-medium** (yellow): Nice to have
- **P3-low** (green): Polish and enhancements
- **P4-reach** (gray): Wishlist items

### Ownership Labels
- **better-for-ai** 🤖: Tasks well-suited for AI assistance
- **better-for-human** 👤: Tasks requiring human judgment/domain expertise
- **collaborative** 🤝: Tasks best done with AI-human collaboration

### Theme Labels
- **strategy**: Strategy development and backtesting
- **testing**: Testing, validation, and quality assurance
- **risk-management**: Risk controls and position management
- **monitoring**: Observability, logging, and alerts
- **infrastructure**: System architecture and deployment
- **analytics**: Performance analysis and reporting
- **code-quality**: Refactoring, type hints, documentation
- **documentation**: Documentation improvements

## Workflow Example

1. **Initial Setup:**
   ```
   /create-labels
   /todo-to-issues
   ```

2. **During Development:**
   - Add new tasks to TODO.md
   - Run `/todo-to-issues` to create GitHub issues
   - Work on issues (close them on GitHub when done)

3. **Stay in Sync:**
   ```
   /sync-todo-issues    # Update TODO.md with latest status
   /issue-stats         # Check progress
   ```

4. **Before Competition:**
   ```
   /issue-stats         # Verify all P0 issues are closed
   ```

## Customization

To modify labels, edit the `create_labels.py` script or the `/create-labels` command file.

To change how issues are categorized, edit the theme detection logic in `create_issues.py` and `add_labels.py`.

## Troubleshooting

**"gh: command not found"**
- Install GitHub CLI: https://cli.github.com/

**"could not add label: not found"**
- Run `/create-labels` first to create the labels

**Issues not syncing**
- Ensure you're authenticated: `gh auth status`
- Check you're in the correct repo: `gh repo view`

## Contributing

Feel free to add more commands and scripts to automate common project management tasks!
