#!/usr/bin/env python3
"""
setup_branch_protection.py - Automated GitHub Branch Protection Ruleset Setup

Applies the repository branch protection ruleset (.github/rulesets/protect-main-branch.json)
to the current GitHub repository using gh CLI api.
Supports --dry-run for offline payload validation.
"""

import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path

def validate_ruleset_file(ruleset_path: Path) -> dict:
    """Validate existence and JSON schema of the branch protection ruleset file."""
    if not ruleset_path.exists():
        raise FileNotFoundError(f"Ruleset file not found: {ruleset_path}")

    try:
        data = json.loads(ruleset_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in ruleset file: {e}")

    required_keys = ['name', 'target', 'enforcement', 'rules']
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key '{key}' in ruleset JSON.")

    return data

def apply_branch_protection(ruleset_path: Path, dry_run: bool = False):
    """Apply GitHub branch protection ruleset via gh CLI api."""
    data = validate_ruleset_file(ruleset_path)
    print(f"🔒 Branch Protection Ruleset: '{data['name']}' (Target: {data['target']})")

    if dry_run:
        print("  🧪 Dry-run mode active. Validated ruleset payload:")
        print(json.dumps(data, indent=2))
        return True

    gh_bin = shutil.which('gh')
    if not gh_bin:
        print("  ⚠️ GitHub CLI (gh) not found in PATH. Skipping branch protection configuration.", file=sys.stderr)
        return False

    # Get current repository repo NWO (owner/repo)
    repo_cmd = [gh_bin, 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner']
    res_repo = subprocess.run(repo_cmd, check=False, capture_output=True, text=True)

    if res_repo.returncode != 0 or not res_repo.stdout.strip():
        print(f"  ⚠️ Could not determine GitHub repository nameWithOwner: {res_repo.stderr.strip()}", file=sys.stderr)
        return False

    nwo = res_repo.stdout.strip()
    api_endpoint = f"repos/{nwo}/rulesets"

    print(f"🚀 Pushing branch protection ruleset to GitHub: {nwo}...")
    api_cmd = [gh_bin, 'api', api_endpoint, '-X', 'POST', '--input', str(ruleset_path)]
    res_api = subprocess.run(api_cmd, check=False, capture_output=True, text=True)

    if res_api.returncode == 0:
        print(f"  ✓ Successfully applied branch protection ruleset to {nwo}")
        return True
    else:
        print(f"  ⚠️ Warning: Failed to apply ruleset via gh api (Exit Code {res_api.returncode}):", file=sys.stderr)
        print(f"     {res_api.stderr.strip()}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Configure GitHub branch protection rulesets.")
    parser.add_argument('--ruleset', type=str, default=None, help='Path to ruleset JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Validate ruleset JSON without sending API request')

    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent.resolve()
    ruleset_path = Path(args.ruleset) if args.ruleset else root_dir / '.github' / 'rulesets' / 'protect-main-branch.json'

    try:
        success = apply_branch_protection(ruleset_path, dry_run=args.dry_run)
        if not success and not args.dry_run:
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
