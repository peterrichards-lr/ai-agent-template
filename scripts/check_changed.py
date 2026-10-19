#!/usr/bin/env python3
"""
check_changed.py - Run the pre-commit gate on changed files only, behind `make check`.

`make verify` is the CI-equivalent gate: every hook over every file, plus the stack's
linters, tests and documentation checks. That is the right gate before a pull request
and the wrong one for an agent's edit-test loop, where re-scanning an unchanged tree on
every iteration costs minutes and tokens for no new information.

`make check` is the inner loop: the pre-commit hooks over the files that differ from the
merge base with BASE_REF (committed, uncommitted and untracked-but-not-ignored), then
`make test`. It is a subset of `make verify`, never a substitute: run `make verify`
before opening a pull request.

Python rather than shell for the same reasons as agent_push.py: file names with spaces
survive, it works on a Windows checkout, and a failure names the hook to fix.

Exit codes: the pre-commit exit code; 2 when the base ref cannot be resolved.
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List

from agent_push import describe_failed_hooks

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_REF = 'origin/main'


def git_lines(args: List[str], cwd: Path) -> List[str]:
    """Run git with NUL-separated output and return the entries."""
    result = subprocess.run(['git', *args], cwd=str(cwd), capture_output=True, check=True)
    return [entry for entry in result.stdout.decode('utf-8').split('\0') if entry]


def changed_files(base_ref: str, cwd: Path) -> List[str]:
    """Files that differ from the merge base with base_ref, plus untracked ones.

    Deleted files are excluded: there is nothing left to check. Raises
    subprocess.CalledProcessError when base_ref cannot be resolved.
    """
    merge_base = subprocess.run(['git', 'merge-base', 'HEAD', base_ref], cwd=str(cwd),
                                capture_output=True, text=True, check=True).stdout.strip()
    modified = git_lines(['diff', '--name-only', '-z', '--diff-filter=d', merge_base], cwd)
    untracked = git_lines(['ls-files', '-z', '--others', '--exclude-standard'], cwd)
    return sorted(set(modified) | set(untracked))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--base', default=os.environ.get('BASE_REF') or DEFAULT_BASE_REF,
                        help=f'ref to diff against via its merge base (default: {DEFAULT_BASE_REF})')
    # The Makefile passes its own resolved $(PRE_COMMIT), so the console-script versus
    # module-form fallback is decided in one place.
    parser.add_argument('--pre-commit', dest='pre_commit', default='pre-commit',
                        help='pre-commit command (default: pre-commit)')
    args = parser.parse_args(argv)

    try:
        files = changed_files(args.base, REPO_ROOT)
    except subprocess.CalledProcessError:
        print(f"❌ make check: cannot find a merge base with '{args.base}'.\n"
              f"   Fetch it (git fetch origin) or name another base: make check BASE_REF=<ref>",
              file=sys.stderr)
        return 2

    if not files:
        print(f"✓ No files changed relative to {args.base}; nothing for the hooks to check.")
        return 0

    print(f"🧪 Running pre-commit on {len(files)} file(s) changed relative to {args.base}...",
          flush=True)
    command = shlex.split(args.pre_commit)
    gate = subprocess.run([*command, 'run', '--files', *files], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, check=False)
    print(gate.stdout, end='')
    if gate.stderr:
        print(gate.stderr, end='', file=sys.stderr)
    if gate.returncode != 0:
        print(f"❌ {describe_failed_hooks(gate.stdout + gate.stderr)}", file=sys.stderr)
    return gate.returncode


if __name__ == '__main__':
    sys.exit(main())
