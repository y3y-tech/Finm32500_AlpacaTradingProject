#!/usr/bin/env python3
"""Remove [P*] prefix from GitHub issue titles."""

import re
import subprocess
import json


def get_all_issues():
    """Get all open issues."""
    cmd = ["gh", "issue", "list", "--json", "number,title", "--limit", "1000"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def remove_priority_prefix(title):
    """Remove [P*] prefix from title."""
    # Match [P0], [P1], [P2], [P3], [P4] at the start
    match = re.match(r"^\[P\d\]\s+(.+)$", title)
    if match:
        return match.group(1)
    return title


def update_issue_title(issue_number, new_title):
    """Update GitHub issue title."""
    cmd = ["gh", "issue", "edit", str(issue_number), "--title", new_title]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error updating issue #{issue_number}: {e.stderr}")
        return False


def main():
    print("Fetching all issues...")
    issues = get_all_issues()
    print(f"Found {len(issues)} issues\n")

    print("Removing [P*] prefixes from issue titles...")
    success_count = 0

    for issue in issues:
        number = issue["number"]
        old_title = issue["title"]
        new_title = remove_priority_prefix(old_title)

        if new_title != old_title:
            if update_issue_title(number, new_title):
                print(f"✓ #{number}: {old_title} → {new_title}")
                success_count += 1
            else:
                print(f"✗ #{number}: Failed to update")
        else:
            print(f"○ #{number}: No prefix to remove")

    print(f"\n✓ Updated {success_count}/{len(issues)} issues")


if __name__ == "__main__":
    main()
