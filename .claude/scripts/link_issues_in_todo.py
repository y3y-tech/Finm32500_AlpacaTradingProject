#!/usr/bin/env python3
"""Add GitHub issue references to TODO.md."""

import re
import subprocess
import json

def get_all_issues():
    """Get all open issues."""
    cmd = ['gh', 'issue', 'list', '--json', 'number,title', '--limit', '1000', '--state', 'open']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def create_title_to_issue_map(issues):
    """Create a mapping from issue titles to issue numbers."""
    title_map = {}
    for issue in issues:
        title = issue['title'].strip()
        number = issue['number']
        title_map[title.lower()] = number
    return title_map

def add_issue_links_to_todo(todo_path, title_map):
    """Add GitHub issue references to TODO.md."""
    with open(todo_path, 'r') as f:
        lines = f.readlines()

    updated_lines = []
    changes_made = 0

    for line in lines:
        # Match task items with emoji and title
        task_match = re.match(r'^(- \[ \] [👤🤖🤝] \*\*)(.+?)(\*\*.*)$', line)
        if task_match:
            prefix = task_match.group(1)
            title = task_match.group(2)
            suffix = task_match.group(3)

            # Check if issue reference already exists
            if not re.search(r'#\d+', line):
                # Try to find matching issue
                title_lower = title.lower().strip()
                if title_lower in title_map:
                    issue_num = title_map[title_lower]
                    # Add issue reference after the title
                    new_line = f"{prefix}{title}{suffix} [#{issue_num}]\n"
                    updated_lines.append(new_line)
                    changes_made += 1
                    print(f"✓ Linked: {title} → #{issue_num}")
                else:
                    updated_lines.append(line)
                    print(f"○ No match: {title}")
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # Write back to file
    with open(todo_path, 'w') as f:
        f.writelines(updated_lines)

    return changes_made

def main():
    todo_file = '/Users/antonio/Documents/finmath/32500-comp-fin-py/group-assignments/Finm32500_AlpacaTradingProject/TODO.md'

    print("Fetching all GitHub issues...")
    issues = get_all_issues()
    print(f"Found {len(issues)} issues\n")

    print("Creating title mapping...")
    title_map = create_title_to_issue_map(issues)

    print("Adding issue references to TODO.md...")
    changes = add_issue_links_to_todo(todo_file, title_map)

    print(f"\n✓ Added {changes} issue references to TODO.md")

if __name__ == '__main__':
    main()
