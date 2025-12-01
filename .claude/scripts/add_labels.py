#!/usr/bin/env python3
"""Add labels to existing GitHub issues based on title and content."""

import subprocess
import json

def get_all_issues():
    """Get all open issues."""
    cmd = ['gh', 'issue', 'list', '--json', 'number,title,body', '--limit', '1000']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def determine_labels(issue):
    """Determine appropriate labels for an issue."""
    title = issue['title']
    body = issue['body'] or ''
    labels = []

    # Priority labels
    if title.startswith('[P0]'):
        labels.append('P0-critical')
    elif title.startswith('[P1]'):
        labels.append('P1-high')
    elif title.startswith('[P2]'):
        labels.append('P2-medium')
    elif title.startswith('[P3]'):
        labels.append('P3-low')
    elif title.startswith('[P4]'):
        labels.append('P4-reach')

    # Theme labels based on keywords
    title_lower = title.lower()
    body_lower = body.lower()

    if any(word in title_lower for word in ['strategy', 'momentum', 'trading', 'pairs', 'arbitrage', 'breakout', 'ensemble']):
        labels.append('strategy')

    if any(word in title_lower for word in ['test', 'validation', 'stress']):
        labels.append('testing')

    if any(word in title_lower for word in ['risk', 'stop-loss', 'circuit breaker', 'position sizing']):
        labels.append('risk-management')

    if any(word in title_lower for word in ['monitor', 'dashboard', 'alert', 'logging']):
        labels.append('monitoring')

    if any(word in title_lower for word in ['alpacatrader', 'livetrading', 'config', 'database', 'shutdown', 'infrastructure']):
        labels.append('infrastructure')

    if any(word in title_lower for word in ['analytics', 'performance attribution', 'trade analytics', 'metrics']):
        labels.append('analytics')

    if any(word in title_lower for word in ['type hints', 'refactor', 'code quality', 'coverage']):
        labels.append('code-quality')

    if any(word in title_lower for word in ['documentation', 'docstring']):
        labels.append('documentation')

    return labels

def add_labels_to_issue(issue_number, labels):
    """Add labels to a GitHub issue."""
    if not labels:
        return True

    cmd = ['gh', 'issue', 'edit', str(issue_number), '--add-label', ','.join(labels)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error adding labels to issue #{issue_number}: {e.stderr}")
        return False

def main():
    print("Fetching all issues...")
    issues = get_all_issues()
    print(f"Found {len(issues)} issues\n")

    print("Adding labels to issues...")
    success_count = 0

    for issue in issues:
        number = issue['number']
        title = issue['title']
        labels = determine_labels(issue)

        if labels:
            if add_labels_to_issue(number, labels):
                print(f"✓ #{number}: {title[:50]}... → {', '.join(labels)}")
                success_count += 1
            else:
                print(f"✗ #{number}: {title[:50]}... → Failed")
        else:
            print(f"○ #{number}: {title[:50]}... → No labels")

    print(f"\n✓ Added labels to {success_count}/{len(issues)} issues")

if __name__ == '__main__':
    main()
