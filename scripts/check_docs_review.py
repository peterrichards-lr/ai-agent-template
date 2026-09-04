#!/usr/bin/env python3
"""
check_docs_review.py - Documentation Freshness & Review Staleness Checker

Validates that all Markdown (.md) documents contain valid timestamp footers
and adhere to maximum review age and update thresholds.
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import datetime

IGNORE_DIRS = {
    '.git', 'node_modules', '.venv', 'venv', 'env', '.smoke_venv',
    'coverage', 'target', 'build', 'dist', 'bin', '.gemini', '.agent_scratch', '.pytest_cache'
}

FOOTER_REGEX = re.compile(
    r"([*_])Last Updated:\s*(\d{4}-\d{2}-\d{2})\1\s*\|\s*\1Last Reviewed:\s*(\d{4}-\d{2}-\d{2})\1"
)
EXTRA_DOC_FILES = ['.cursorrules', '.windsurfrules']

def strip_code_fences(content: str) -> str:
    """Strip fenced code blocks (```...```) to prevent illustrative examples from being parsed as footers."""
    return re.sub(r'```[\s\S]*?```', '', content)

def should_ignore(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    return False

def parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str.strip(), '%Y-%m-%d')
    except ValueError as e:
        print(f"Error parsing date '{date_str}': {e}", file=sys.stderr)
        raise

def check_docs(max_review_days: int, max_update_days: int, max_gap_days: int, root_dir: Path = None) -> bool:
    if root_dir is None:
        root_dir = Path(__file__).parent.parent.resolve()

    today = datetime.today()
    violations = []
    scanned_count = 0

    extra_files = [root_dir / f for f in EXTRA_DOC_FILES if (root_dir / f).exists()]
    for doc_path in list(root_dir.rglob('*.md')) + extra_files:
        if should_ignore(doc_path):
            continue

        scanned_count += 1
        content = doc_path.read_text(encoding='utf-8')
        rel_path = doc_path.relative_to(root_dir)

        content_outside_code = strip_code_fences(content)
        matches = list(FOOTER_REGEX.finditer(content_outside_code))

        if not matches:
            print(f"Violation: {rel_path} is missing a valid timestamp footer block.", file=sys.stderr)
            violations.append(str(rel_path))
            continue

        if len(matches) > 1:
            print(f"Violation: {rel_path} contains {len(matches)} duplicate timestamp footers.", file=sys.stderr)
            violations.append(str(rel_path))
            continue

        match = matches[0]
        try:
            last_updated_date = parse_date(match.group(2))
            last_reviewed_date = parse_date(match.group(3))
        except Exception:
            violations.append(str(rel_path))
            continue

        review_days = (today - last_reviewed_date).days
        update_days = (today - last_updated_date).days
        gap_days = abs((last_reviewed_date - last_updated_date).days)

        if review_days > max_review_days:
            print(f"Violation: {rel_path} last reviewed {review_days} days ago (limit: {max_review_days} days).", file=sys.stderr)
            violations.append(str(rel_path))

        if update_days > max_update_days:
            print(f"Violation: {rel_path} last updated {update_days} days ago (limit: {max_update_days} days).", file=sys.stderr)
            violations.append(str(rel_path))

        if gap_days > max_gap_days:
            print(f"Violation: {rel_path} gap between update and review is {gap_days} days (limit: {max_gap_days} days).", file=sys.stderr)
            violations.append(str(rel_path))

    if violations:
        print(f"\nFound {len(violations)} document review policy violations across {scanned_count} files.", file=sys.stderr)
        return False

    print(f"All {scanned_count} Markdown documents conform to the documentation review policy.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Check Markdown files for review policy adherence.")
    parser.add_argument('--max-review-days', type=int, default=180, help='Maximum allowed days since last review')
    parser.add_argument('--max-update-days', type=int, default=180, help='Maximum allowed days since last update')
    parser.add_argument('--max-gap-days', type=int, default=180, help='Maximum allowed gap in days between update and review')
    parser.add_argument('--dir', type=str, default=None, help='Target directory path to check')

    args = parser.parse_args()
    target_dir = Path(args.dir).resolve() if args.dir else None

    success = check_docs(
        max_review_days=args.max_review_days,
        max_update_days=args.max_update_days,
        max_gap_days=args.max_gap_days,
        root_dir=target_dir
    )

    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main()
