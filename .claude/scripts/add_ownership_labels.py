#!/usr/bin/env python3
"""Add ownership labels to GitHub issues based on TODO.md."""

import re
import subprocess

def parse_todo_with_ownership(filepath):
    """Parse TODO.md and extract task titles with ownership indicators."""
    with open(filepath, 'r') as f:
        content = f.read()

    task_ownership = {}
    lines = content.split('\n')

    for line in lines:
        # Match task items with emoji and title
        task_match = re.match(r'^- \[ \] ([👤🤖🤝]) \*\*(.+?)\*\*', line)
        if task_match:
            emoji = task_match.group(1)
            title = task_match.group(2)

            # Map emoji to ownership label
            if emoji == '🤖':
                ownership = 'better-for-ai'
            elif emoji == '👤':
                ownership = 'better-for-human'
            elif emoji == '🤝':
                ownership = 'collaborative'
            else:
                ownership = None

            if ownership:
                task_ownership[title] = ownership

    return task_ownership

def get_all_issues():
    """Get all open issues."""
    cmd = ['gh', 'issue', 'list', '--json', 'number,title', '--limit', '1000', '--state', 'open']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    import json
    return json.loads(result.stdout)

def add_label_to_issue(issue_number, label):
    """Add a label to a GitHub issue."""
    cmd = ['gh', 'issue', 'edit', str(issue_number), '--add-label', label]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error adding label to issue #{issue_number}: {e.stderr}")
        return False

def main():
    todo_file = '/Users/antonio/Documents/finmath/32500-comp-fin-py/group-assignments/Finm32500_AlpacaTradingProject/TODO.md'

    print("Parsing TODO.md for ownership information...")
    task_ownership = parse_todo_with_ownership(todo_file)
    print(f"Found {len(task_ownership)} tasks with ownership indicators\n")

    print("Fetching all GitHub issues...")
    issues = get_all_issues()
    print(f"Found {len(issues)} issues\n")

    print("Adding ownership labels to issues...")
    success_count = 0
    matched_count = 0

    for issue in issues:
        number = issue['number']
        title = issue['title']

        # Try to match issue title with TODO task
        matched = False
        ownership_label = None

        for task_title, ownership in task_ownership.items():
            # Normalize for comparison (case-insensitive, ignore extra spaces)
            if task_title.lower().strip() in title.lower().strip() or \
               title.lower().strip() in task_title.lower().strip():
                ownership_label = ownership
                matched = True
                break

        if matched and ownership_label:
            if add_label_to_issue(number, ownership_label):
                print(f"✓ #{number}: {title[:50]}... → {ownership_label}")
                success_count += 1
                matched_count += 1
            else:
                print(f"✗ #{number}: Failed to add label")
        else:
            print(f"○ #{number}: {title[:50]}... → No ownership match")

    print(f"\n✓ Added ownership labels to {success_count}/{len(issues)} issues")
    print(f"✓ Matched {matched_count} tasks from TODO.md")

if __name__ == '__main__':
    main()
