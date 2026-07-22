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

def run_gh_command(cmd_args):
    result = subprocess.run(['gh'] + cmd_args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing gh CLI: {result.stderr.strip()}", file=sys.stderr)
        return None
    return result.stdout.strip()

def sync_issues(plan_file: Path, dry_run: bool = False):
    if not plan_file.exists():
        print(f"Task plan file not found: {plan_file}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(plan_file.read_text(encoding='utf-8'))
    tasks = data.get('tasks', [])
    epic_title = data.get('epic', {}).get('title', 'AI Agent Task Plan')
    
    print(f"Loaded {len(tasks)} tasks for Epic: '{epic_title}'")
    
    for task in tasks:
        title = task.get('title')
        body = task.get('body', '')
        labels = task.get('labels', ['task'])
        
        if dry_run:
            print(f"[DRY-RUN] Would create issue: '{title}' with labels: {labels}")
        else:
            print(f"Creating GitHub issue: '{title}'...")
            label_args = []
            for l in labels:
                label_args.extend(['--label', l])
                
            cmd = ['issue', 'create', '--title', title, '--body', body] + label_args
            out = run_gh_command(cmd)
            if out:
                print(f"  ✓ Created: {out}")

def main():
    parser = argparse.ArgumentParser(description="Synchronise JSON task plans with GitHub Issues.")
    parser.add_argument('plan_file', type=str, help='Path to JSON task plan file')
    parser.add_argument('--dry-run', action='store_true', help='Preview actions without calling gh CLI')
    
    args = parser.parse_args()
    sync_issues(Path(args.plan_file), args.dry_run)

if __name__ == '__main__':
    main()
