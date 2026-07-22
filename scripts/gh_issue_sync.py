#!/usr/bin/env python3
"""
gh_issue_sync.py - GitHub Issue & Task Plan Synchronizer

Parses a structured JSON task plan file and creates/updates GitHub Issues
using the GitHub CLI (`gh`).
"""

import sys
import json
import subprocess
import argparse
from pathlib import Path

def run_gh_command(cmd_args: list[str], timeout: int = 30):
    """Execute a gh CLI command with explicit timeout and error boundaries."""
    try:
        result = subprocess.run(
            ['gh'] + cmd_args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            print(f"❌ Error executing gh CLI: {result.stderr.strip()}", file=sys.stderr)
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout ({timeout}s) expired while running gh CLI command.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ Error invoking gh CLI: {e}", file=sys.stderr)
        return None

def sync_issues(plan_file: Path, dry_run: bool = False):
    if not plan_file.exists():
        print(f"❌ Task plan file not found: {plan_file}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(plan_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse task plan JSON: {e}", file=sys.stderr)
        sys.exit(1)

    tasks = data.get('tasks', [])
    if not isinstance(tasks, list):
        print("❌ Task plan 'tasks' field must be a list.", file=sys.stderr)
        sys.exit(1)

    epic_title = data.get('epic', {}).get('title', 'AI Agent Task Plan')
    print(f"📋 Loaded {len(tasks)} tasks for Epic: '{epic_title}'")

    created_count = 0
    for idx, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            print(f"⚠️ Task #{idx} is invalid (not a JSON object). Skipping.")
            continue

        title = task.get('title')
        if not title or not isinstance(title, str) or not title.strip():
            print(f"⚠️ Task #{idx} is missing a valid title string. Skipping.")
            continue

        body = task.get('body', '')
        labels = task.get('labels', ['task'])

        if dry_run:
            print(f"[DRY-RUN] Task #{idx}: Would create issue '{title.strip()}' with labels: {labels}")
            created_count += 1
        else:
            print(f"Creating GitHub issue #{idx}: '{title.strip()}'...")
            label_args = []
            for l in labels:
                label_args.extend(['--label', str(l)])

            cmd = ['issue', 'create', '--title', title.strip(), '--body', str(body)] + label_args
            out = run_gh_command(cmd)
            if out:
                print(f"  ✓ Created: {out}")
                created_count += 1

    print(f"✅ Processed {created_count} of {len(tasks)} tasks.")

def main():
    parser = argparse.ArgumentParser(description="Synchronise JSON task plans with GitHub Issues.")
    parser.add_argument('plan_file', type=str, help='Path to JSON task plan file')
    parser.add_argument('--dry-run', action='store_true', help='Preview actions without calling gh CLI')

    args = parser.parse_args()
    sync_issues(Path(args.plan_file), args.dry_run)

if __name__ == '__main__':
    main()
