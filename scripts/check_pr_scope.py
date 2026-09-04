#!/usr/bin/env python3
"""
check_pr_scope.py - Pull Request Scope Sprawl Guardrail

Enforces that bugfix PRs modify no more than 10 files unless an explicit,
auditable bypass label ('bypass-sprawl') is applied.

Empirical grounding:
Across all 30 merged PRs in this repository, the largest bugfix touched 6 files
(#66, #63, #62). The default threshold of 10 files provides ~40% headroom above
the largest historical bugfix while preventing massive drive-by refactorings.

File count definition:
Every unique file path present in the PR diff (additions, modifications, renames,
and deletions) counts toward the total.
"""

import argparse
import re
import sys
from typing import List, Tuple

# Conventional-commit scoped (fix(scope): ...) or bare (fix: ...) titles
BUGFIX_TITLE_REGEX = re.compile(r'^(fix|bugfix|bug)(\([^)]*\))?:', re.IGNORECASE)
# Slash-style (fix/foo) or dash-style (fix-foo) branches
BUGFIX_BRANCH_REGEX = re.compile(r'^(fix|bugfix)[/-]', re.IGNORECASE)

BYPASS_LABEL = "bypass-sprawl"
DEFAULT_MAX_FILES = 10


def is_bugfix_pr(branch: str, title: str) -> bool:
    """Determine whether a PR is classified as a bugfix based on branch or title."""
    return bool(BUGFIX_BRANCH_REGEX.search(branch or "") or BUGFIX_TITLE_REGEX.search(title or ""))


def validate_pr_scope(
    branch: str,
    title: str,
    labels: List[str],
    changed_count: int,
    max_files: int = DEFAULT_MAX_FILES,
) -> Tuple[bool, str]:
    """Validate PR size against the scope sprawl guardrail."""
    if not is_bugfix_pr(branch, title):
        return True, "Non-bugfix PR: scope sprawl check not applicable."

    # Normalize labels
    normalized_labels = {lbl.strip().lower() for lbl in (labels or [])}
    if BYPASS_LABEL in normalized_labels:
        return True, f"Scope sprawl check bypassed via '{BYPASS_LABEL}' label."

    if changed_count > max_files:
        return (
            False,
            f"Scope Sprawl Gate: Bugfix PR modifies {changed_count} files (limit is {max_files}). "
            f"Please break down changes into smaller, atomic contributions or have a maintainer "
            f"apply the '{BYPASS_LABEL}' label if this scope is strictly necessary.",
        )

    return True, f"Scope Sprawl Gate: Bugfix PR modifies {changed_count} files (limit is {max_files}). Passed."


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce PR scope sprawl guardrail for bugfixes.")
    parser.add_argument("--branch", default="", help="PR head branch name")
    parser.add_argument("--title", default="", help="PR title")
    parser.add_argument("--labels", default="", help="Newline- or comma-separated PR labels")
    parser.add_argument("--changed-count", type=int, default=0, help="Number of files modified in the PR")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="Maximum allowed files for a bugfix")

    args = parser.parse_args()

    label_list = [l.strip() for l in re.split(r'[,\n]', args.labels) if l.strip()]
    passed, message = validate_pr_scope(
        branch=args.branch,
        title=args.title,
        labels=label_list,
        changed_count=args.changed_count,
        max_files=args.max_files,
    )

    if passed:
        print(f"✓ {message}")
        return 0
    else:
        print(f"✗ {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
