#!/usr/bin/env python3
"""Sync TODO.md checkbox status with GitHub issue status."""

import re
import subprocess
import json

def get_issue_status(issue_number):
    """Get the status of a GitHub issue (open/closed)."""
    cmd = ['gh', 'issue', 'view', str(issue_number), '--json', 'state']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data['state'].upper()  # OPEN or CLOSED
    except subprocess.CalledProcessError:
        return None

def sync_todo_with_github(todo_path):
    """Sync TODO.md checkboxes with GitHub issue status."""
    with open(todo_path, 'r') as f:
        lines = f.readlines()

    updated_lines = []
    changes_made = 0
    stats = {'checked': 0, 'unchecked': 0, 'closed': 0, 'open': 0, 'not_found': 0}

    for line in lines:
        # Match tasks with issue references
        task_match = re.match(r'^- \[([ x])\] (.+?) \[#(\d+)\]', line)
        if task_match:
            current_check = task_match.group(1)
            task_content = task_match.group(2)
            issue_num = int(task_match.group(3))

            # Get GitHub issue status
            gh_status = get_issue_status(issue_num)

            if gh_status is None:
                print(f"⚠ #{issue_num}: Issue not found")
                updated_lines.append(line)
                stats['not_found'] += 1
            elif gh_status == 'CLOSED':
                stats['closed'] += 1
                if current_check != 'x':
                    # Update to checked
                    new_line = line.replace(f'- [ ] {task_content}', f'- [x] {task_content}')
                    updated_lines.append(new_line)
                    changes_made += 1
                    print(f"✓ #{issue_num}: Marked as complete (closed on GitHub)")
                else:
                    updated_lines.append(line)
                    stats['checked'] += 1
            else:  # OPEN
                stats['open'] += 1
                if current_check == 'x':
                    # Update to unchecked
                    new_line = line.replace(f'- [x] {task_content}', f'- [ ] {task_content}')
                    updated_lines.append(new_line)
                    changes_made += 1
                    print(f"○ #{issue_num}: Marked as incomplete (reopened on GitHub)")
                else:
                    updated_lines.append(line)
                    stats['unchecked'] += 1
        else:
            updated_lines.append(line)

    # Write back to file
    if changes_made > 0:
        with open(todo_path, 'w') as f:
            f.writelines(updated_lines)

    return changes_made, stats

def main():
    todo_file = 'TODO.md'

    print("Syncing TODO.md with GitHub issue status...")
    changes, stats = sync_todo_with_github(todo_file)

    print(f"\n{'='*50}")
    print("Sync Summary:")
    print(f"{'='*50}")
    print(f"Total issues found: {stats['open'] + stats['closed']}")
    print(f"  ✓ Closed on GitHub: {stats['closed']}")
    print(f"  ○ Open on GitHub: {stats['open']}")
    if stats['not_found'] > 0:
        print(f"  ⚠ Not found: {stats['not_found']}")
    print(f"\nChanges made: {changes}")
    if changes == 0:
        print("✓ TODO.md is already in sync with GitHub!")

if __name__ == '__main__':
    main()
