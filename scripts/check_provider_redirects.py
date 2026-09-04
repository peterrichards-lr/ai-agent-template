#!/usr/bin/env python3
"""
check_provider_redirects.py - Validate Thin AI Provider Redirect Files

Ensures provider discovery files (.cursorrules, .windsurfrules,
.github/copilot-instructions.md, CLAUDE.md, GEMINI.md) exist, stay thin (<25 lines),
and explicitly link to AGENTS.md.
"""

import sys
from pathlib import Path

MAX_REDIRECT_LINES = 25
REDIRECT_FILES = [
    'CLAUDE.md',
    'GEMINI.md',
    '.cursorrules',
    '.windsurfrules',
    '.github/copilot-instructions.md',
]

def check_redirects(root_dir: Path = None) -> bool:
    if root_dir is None:
        root_dir = Path(__file__).parent.parent.resolve()

    violations = []
    for rel_path in REDIRECT_FILES:
        path = root_dir / rel_path
        if not path.exists():
            violations.append(f"Missing provider redirect file: {rel_path}")
            continue

        content = path.read_text(encoding='utf-8')
        lines = content.splitlines()

        if len(lines) >= MAX_REDIRECT_LINES:
            violations.append(
                f"{rel_path} exceeds maximum length of {MAX_REDIRECT_LINES} lines "
                f"({len(lines)} lines). Redirects must remain thin and free of duplicated rules."
            )

        if 'AGENTS.md' not in content:
            violations.append(
                f"{rel_path} does not link/redirect to AGENTS.md."
            )

    if violations:
        print("❌ Provider discovery redirect check failed:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return False

    print(f"✓ All {len(REDIRECT_FILES)} provider redirect files are thin (<{MAX_REDIRECT_LINES} lines) and link to AGENTS.md.")
    return True

if __name__ == '__main__':
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    if not check_redirects(target):
        sys.exit(1)
