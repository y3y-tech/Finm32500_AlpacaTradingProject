#!/usr/bin/env python3
"""Parse TODO.md and create GitHub issues."""

import re
import subprocess
import sys

def parse_todo_file(filepath):
    """Parse TODO.md and extract tasks."""
    with open(filepath, 'r') as f:
        content = f.read()

    issues = []
    current_section = None
    current_priority = None
    current_task = None

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect priority sections
        if line.startswith('## 🚨 P0'):
            current_priority = 'P0-critical'
            current_section = 'Critical'
        elif line.startswith('## 📊 P1'):
            current_priority = 'P1-high'
            current_section = 'High Priority'
        elif line.startswith('## 🔧 P2'):
            current_priority = 'P2-medium'
            current_section = 'Medium Priority'
        elif line.startswith('## 🎨 P3'):
            current_priority = 'P3-low'
            current_section = 'Low Priority'
        elif line.startswith('## 🚀 P4'):
            current_priority = 'P4-reach'
            current_section = 'Reach Goals'

        # Detect task items (- [ ] with emoji and bold title)
        task_match = re.match(r'^- \[ \] [👤🤖🤝] \*\*(.+?)\*\*', line)
        if task_match and current_priority:
            title = task_match.group(1)

            # Collect description lines
            description_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith('- [ ]'):
                desc_line = lines[i].strip()
                if desc_line and not desc_line.startswith('##'):
                    description_lines.append(desc_line)
                elif desc_line.startswith('##'):
                    i -= 1
                    break
                i += 1

            # Clean up description
            description = '\n'.join(description_lines)

            # Determine labels
            labels = [current_priority]
            if 'strategy' in title.lower() or 'Strategy' in description:
                labels.append('strategy')
            if 'test' in title.lower() or 'Testing' in description:
                labels.append('testing')
            if 'risk' in title.lower() or 'Risk' in description:
                labels.append('risk-management')
            if 'monitor' in title.lower() or 'dashboard' in title.lower():
                labels.append('monitoring')

            issues.append({
                'title': f"[{current_priority.split('-')[0]}] {title}",
                'body': description,
                'labels': labels
            })
            continue

        i += 1

    return issues

def create_github_issue(issue):
    """Create a GitHub issue using gh CLI."""
    title = issue['title']
    body = issue['body']
    labels = ','.join(issue['labels'])

    # Create issue without labels first
    cmd = ['gh', 'issue', 'create', '--title', title, '--body', body]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Created: {title}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create: {title}")
        print(f"  Error: {e.stderr}")
        return False

def main():
    todo_file = '/Users/antonio/Documents/finmath/32500-comp-fin-py/group-assignments/Finm32500_AlpacaTradingProject/TODO.md'

    print("Parsing TODO.md...")
    issues = parse_todo_file(todo_file)
    print(f"Found {len(issues)} tasks to convert to issues\n")

    print("\nCreating issues...")
    success_count = 0
    for issue in issues:
        if create_github_issue(issue):
            success_count += 1

    print(f"\n✓ Created {success_count}/{len(issues)} issues successfully")

if __name__ == '__main__':
    main()
