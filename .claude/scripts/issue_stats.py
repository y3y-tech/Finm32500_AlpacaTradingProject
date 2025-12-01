#!/usr/bin/env python3
"""Display statistics about GitHub issues."""

import subprocess
import json
from collections import defaultdict


def get_all_issues(state="all"):
    """Get all issues."""
    cmd = [
        "gh",
        "issue",
        "list",
        "--json",
        "number,title,state,labels",
        "--limit",
        "1000",
        "--state",
        state,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def categorize_issues(issues):
    """Categorize issues by priority, ownership, and theme."""
    stats = {
        "total": len(issues),
        "open": 0,
        "closed": 0,
        "priority": defaultdict(int),
        "ownership": defaultdict(int),
        "theme": defaultdict(int),
    }

    priority_open = defaultdict(list)
    ai_ready = []

    for issue in issues:
        state = issue["state"]
        labels = [l["name"] for l in issue["labels"]]

        if state == "OPEN":
            stats["open"] += 1
        else:
            stats["closed"] += 1

        # Count by priority
        for label in labels:
            if label.startswith("P"):
                stats["priority"][label] += 1
                if state == "OPEN":
                    priority_open[label].append(issue)

        # Count by ownership
        if "better-for-ai" in labels:
            stats["ownership"]["better-for-ai"] += 1
            if state == "OPEN":
                ai_ready.append(issue)
        elif "better-for-human" in labels:
            stats["ownership"]["better-for-human"] += 1
        elif "collaborative" in labels:
            stats["ownership"]["collaborative"] += 1

        # Count by theme
        theme_labels = [
            "strategy",
            "testing",
            "risk-management",
            "monitoring",
            "infrastructure",
            "analytics",
            "code-quality",
            "documentation",
        ]
        for theme in theme_labels:
            if theme in labels:
                stats["theme"][theme] += 1

    return stats, priority_open, ai_ready


def print_stats(stats, priority_open, ai_ready):
    """Print formatted statistics."""
    print("=" * 60)
    print("GitHub Issues Statistics")
    print("=" * 60)

    # Overall stats
    print("\n📊 Overall Status:")
    print(f"  Total Issues: {stats['total']}")
    print(
        f"  ✓ Closed: {stats['closed']} ({stats['closed'] / stats['total'] * 100:.1f}%)"
    )
    print(f"  ○ Open: {stats['open']} ({stats['open'] / stats['total'] * 100:.1f}%)")

    # Priority breakdown
    print("\n🎯 By Priority:")
    for priority in ["P0-critical", "P1-high", "P2-medium", "P3-low", "P4-reach"]:
        total = stats["priority"][priority]
        open_count = len(priority_open.get(priority, []))
        closed = total - open_count
        if total > 0:
            completion = closed / total * 100
            bar = "█" * int(completion / 5) + "░" * (20 - int(completion / 5))
            print(f"  {priority:15} {bar} {closed:2}/{total:2} ({completion:5.1f}%)")

    # Ownership breakdown
    print("\n👥 By Ownership:")
    for ownership, count in sorted(stats["ownership"].items()):
        emoji = "🤖" if "ai" in ownership else "👤" if "human" in ownership else "🤝"
        print(f"  {emoji} {ownership:20} {count:2}")

    # Theme breakdown
    print("\n🏷️  By Theme:")
    for theme, count in sorted(
        stats["theme"].items(), key=lambda x: x[1], reverse=True
    ):
        if count > 0:
            print(f"  {theme:20} {count:2}")

    # Critical open issues
    if priority_open.get("P0-critical"):
        print(f"\n🚨 Open P0 Critical Issues ({len(priority_open['P0-critical'])}):")
        for issue in priority_open["P0-critical"][:5]:
            print(f"  #{issue['number']:3} {issue['title'][:50]}")
        if len(priority_open["P0-critical"]) > 5:
            print(f"  ... and {len(priority_open['P0-critical']) - 5} more")

    # AI-ready issues
    if ai_ready:
        print(f"\n🤖 AI-Ready Open Issues ({len(ai_ready)}):")
        for issue in ai_ready[:5]:
            labels = [l["name"] for l in issue["labels"]]
            priority = (
                [l for l in labels if l.startswith("P")][0]
                if any(l.startswith("P") for l in labels)
                else "?"
            )
            print(f"  [{priority}] #{issue['number']:3} {issue['title'][:45]}")
        if len(ai_ready) > 5:
            print(f"  ... and {len(ai_ready) - 5} more")

    print("\n" + "=" * 60)


def main():
    print("Fetching GitHub issues...")
    issues = get_all_issues()

    stats, priority_open, ai_ready = categorize_issues(issues)
    print_stats(stats, priority_open, ai_ready)


if __name__ == "__main__":
    main()
