#!/usr/bin/env python3
"""
agent_push.py - Guarded Commit-and-Push Entrypoint Behind `make push`

Agents get git wrong in a small number of repeatable ways, and every one of them
ends with the agent reporting success:

- staging nothing, committing nothing, pushing an empty branch, declaring done;
- treating a bare `-m` as the commit message subject, so the real message is lost;
- reaching for the whole-gate bypass when a single pre-commit hook fails.

This script turns each of those into a non-zero exit with an actionable message. It
is invoked through `make push` so adopters get one entrypoint vocabulary rather than
two, and it is Python rather than shell so the guards are unit-testable and work on
a Windows checkout.

The quality gate is never bypassed here. CONTRIBUTING.md forbids the wholesale
bypass flag; when a hook fails this script names the failing hook and prints the
targeted `SKIP=<hook-id>` form instead.

`--force-with-lease` is the sanctioned force form. `.claude/settings.json` denies
bare force pushes positionally and deliberately leaves the lease variant permitted:
it refuses to overwrite a remote that moved since you last fetched, which is the
property that makes it safe. That is recorded here so a later tightening of the
deny-list does not remove it by accident.

Usage:
    make push MESSAGE="feat(scope): what changed"
    make push                       # push already-committed work
    make push PUSH_ARGS=--force-with-lease
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Run before a commit exists, so an unattributable author email is a `git config`
# fix rather than a history rewrite after a ruleset has blocked the merge. See #35.
ATTRIBUTION_SCRIPT_RELPATH = Path('scripts') / 'check_commit_attribution.py'

PRE_COMMIT_CONFIG_RELPATH = Path('.pre-commit-config.yaml')

# Named so the prohibition is greppable and testable rather than a prose rule only.
NO_VERIFY_FLAG = '--no-verify'

HOOK_ID_REGEX = re.compile(r'^-\s*hook id:\s*(\S+)\s*$')

# Porcelain v1 marks untracked entries with '?' in the index column.
UNTRACKED_INDEX_STATUS = '?'
UNMODIFIED_STATUS = ' '


def run_git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git subcommand non-interactively and capture its output."""
    return subprocess.run(
        ['git', *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def classify_worktree(porcelain_output: str) -> Tuple[List[str], List[str], List[str]]:
    """Split `git status --porcelain` output into staged, unstaged and untracked paths.

    A path modified in both the index and the working tree appears in staged *and*
    unstaged: committing it would capture only half of what the agent just wrote,
    which is precisely the silent partial commit the staging guard exists to stop.
    """
    staged, unstaged, untracked = [], [], []

    for line in porcelain_output.splitlines():
        if len(line) < 3:
            continue

        index_status, worktree_status, path = line[0], line[1], line[3:].strip()
        # Renames are reported as 'old -> new'; the new path is the one to report.
        if ' -> ' in path:
            path = path.split(' -> ')[-1].strip()
        path = path.strip('"')

        if index_status == UNTRACKED_INDEX_STATUS:
            untracked.append(path)
            continue
        if index_status != UNMODIFIED_STATUS:
            staged.append(path)
        if worktree_status != UNMODIFIED_STATUS:
            unstaged.append(path)

    return staged, unstaged, untracked


def validate_commit_message(message: Optional[str]) -> Optional[str]:
    """Return an error describing why `message` is unusable, or None when it is fine.

    The flag-shaped check is the #34 failure mode: an argument-handling slip turns a
    forgotten message into a commit whose subject is literally `-m`, which then has to
    be amended out of already-pushed history.
    """
    if message is None or not message.strip():
        return "the commit message is empty"
    if message.strip().startswith('-'):
        return (f"the commit message {message.strip()!r} looks like a command-line flag, "
                "not a subject line")
    return None


def determine_push_plan(
    staged: List[str],
    unstaged: List[str],
    unpushed_count: int,
    message: Optional[str],
) -> Tuple[bool, str]:
    """Decide whether this push may proceed, and explain the refusal when it may not."""
    if unstaged:
        return False, (
            "Refusing to push: these tracked files are modified but not staged, so the "
            "commit would silently omit them:\n"
            + "".join(f"    {path}\n" for path in unstaged)
            + "  Stage them (git add <path>), revert them, or stash them, then retry."
        )

    if not staged and unpushed_count == 0:
        return False, (
            "Refusing to push: nothing is staged and nothing is unpushed, so this push "
            "would be a no-op reported as success.\n"
            "  Stage the work first (git add <path>), then: make push MESSAGE=\"...\""
        )

    if staged:
        error = validate_commit_message(message)
        if error:
            return False, (
                f"Refusing to commit: {error}.\n"
                "  Supply one: make push MESSAGE=\"feat(scope): what changed\""
            )
        return True, f"Commit {len(staged)} staged file(s), then push."

    return True, f"Push {unpushed_count} already-committed change(s)."


def describe_failed_hooks(pre_commit_output: str) -> str:
    """Name the pre-commit hooks that failed and offer the targeted skip form.

    A raw wall of hook output leaves an agent guessing, and the guess is usually the
    wholesale bypass. Naming the hook makes the narrow, auditable escape the obvious one.
    """
    failed_hook_ids = []
    previous_line_failed = False

    for line in pre_commit_output.splitlines():
        match = HOOK_ID_REGEX.match(line.strip())
        if match and previous_line_failed:
            failed_hook_ids.append(match.group(1))
            previous_line_failed = False
            continue
        if line.rstrip().endswith('Failed'):
            previous_line_failed = True

    if not failed_hook_ids:
        return ("Pre-commit reported a failure but named no hook id. Re-run "
                "`pre-commit run --all-files` and read the output above.")

    skip_value = ','.join(failed_hook_ids)
    return (
        "Pre-commit failed in: " + ', '.join(failed_hook_ids) + "\n"
        "  Fix the hook. If it fails only because a tool is missing locally, skip that\n"
        "  hook alone -- never the whole gate:\n"
        f"    SKIP={skip_value} git commit -m \"...\""
    )


def current_branch(cwd: Path) -> str:
    return run_git(['rev-parse', '--abbrev-ref', 'HEAD'], cwd).stdout.strip()


def upstream_ref(cwd: Path) -> Optional[str]:
    """The configured upstream as 'remote/branch', or None when there is none."""
    result = run_git(
        ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}'], cwd)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def upstream_tracks_this_branch(upstream: Optional[str], branch: str) -> bool:
    """Whether a bare `git push` would do the obvious thing.

    `git checkout -b topic origin/main` -- the standard way to start work -- leaves the
    upstream pointing at a *differently named* branch. A bare `git push` then aborts with
    "the upstream branch of your current branch does not match the name of your current
    branch" rather than publishing the topic branch, so an upstream merely existing is
    not enough to skip --set-upstream. Remote names cannot contain '/', so the first
    segment is the remote and the rest is the branch.
    """
    if not upstream:
        return False
    remote, _, upstream_branch = upstream.partition('/')
    return bool(remote) and upstream_branch == branch


def count_unpushed_commits(cwd: Path, upstream: Optional[str], branch: str) -> int:
    """Count commits on HEAD that no remote already has.

    Uses the upstream range only when the upstream actually tracks this branch; otherwise
    'reachable from HEAD but from no remote ref' is the honest measure, and it also covers
    a branch that has never been published.
    """
    if upstream_tracks_this_branch(upstream, branch):
        counted = run_git(['rev-list', '--count', f'{upstream}..HEAD'], cwd)
    else:
        # HEAD before --not: everything after --not is negated, so `--not --remotes HEAD`
        # would exclude HEAD too and count zero on a branch full of unpushed work.
        counted = run_git(['rev-list', '--count', 'HEAD', '--not', '--remotes'], cwd)

    if counted.returncode != 0:
        return 0
    return int(counted.stdout.strip() or 0)


def fail(message: str) -> int:
    print(f"❌ {message}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Guarded commit-and-push. Invoke through `make push`.",
        epilog=("Refuses no-op pushes, refuses to commit while tracked files are still "
                "unstaged, and always runs the pre-commit quality gate."))
    parser.add_argument('-m', '--message', type=str, default=None,
                        help='Commit message subject for the staged changes')
    parser.add_argument('--force-with-lease', action='store_true',
                        help='Push with --force-with-lease, the sanctioned force form')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the guards and the commands that would run, changing nothing')
    args = parser.parse_args(argv)

    cwd = Path.cwd()
    if run_git(['rev-parse', '--is-inside-work-tree'], cwd).returncode != 0:
        return fail(f"{cwd} is not inside a git working tree.")

    # 1. Attribution first, while the fix is still a one-line `git config`.
    attribution = REPO_ROOT / ATTRIBUTION_SCRIPT_RELPATH
    if attribution.exists():
        print("🔍 Checking commit author attribution...", flush=True)
        if subprocess.run([sys.executable, str(attribution)], cwd=str(cwd), check=False).returncode != 0:
            return fail("Commit author attribution check failed (see above); nothing was committed.")

    # 2. Pre-flight staging guard.
    status = run_git(['status', '--porcelain'], cwd)
    if status.returncode != 0:
        return fail(f"git status failed: {status.stderr.strip()}")

    branch = current_branch(cwd)
    upstream = upstream_ref(cwd)
    staged, unstaged, untracked = classify_worktree(status.stdout)
    unpushed_count = count_unpushed_commits(cwd, upstream, branch)
    message = args.message if (args.message or '').strip() else None

    if untracked:
        print("  ⚠️ Untracked files are present and will NOT be committed: "
              + ', '.join(untracked))

    allowed, explanation = determine_push_plan(staged, unstaged, unpushed_count, message)
    if not allowed:
        return fail(explanation)
    print(f"  ✓ Pre-flight guards passed. {explanation}")

    push_command = ['git', 'push']
    if args.force_with_lease:
        push_command.append('--force-with-lease')
    if not upstream_tracks_this_branch(upstream, branch):
        remote = upstream.partition('/')[0] if upstream else 'origin'
        push_command.extend(['--set-upstream', remote, branch])

    if args.dry_run:
        if staged:
            print("  [dry-run] would run: pre-commit run --all-files")
            print(f"  [dry-run] would run: git commit -m {message!r}")
        print(f"  [dry-run] would run: {' '.join(push_command)}")
        return 0

    # 3. Quality gate, then the commit. Never the wholesale bypass.
    if staged:
        if (cwd / PRE_COMMIT_CONFIG_RELPATH).exists():
            print("🧪 Running pre-commit quality gate...", flush=True)
            gate = subprocess.run(['pre-commit', 'run', '--all-files'],
                                  cwd=str(cwd), capture_output=True, text=True, check=False)
            print(gate.stdout, end='')
            if gate.stderr:
                print(gate.stderr, end='', file=sys.stderr)
            if gate.returncode != 0:
                return fail(describe_failed_hooks(gate.stdout + gate.stderr))

        print("📝 Creating commit...", flush=True)
        commit = run_git(['commit', '-m', message], cwd)
        print(commit.stdout, end='')
        if commit.returncode != 0:
            return fail(f"git commit failed: {commit.stderr.strip()}")

    print(f"🚀 {' '.join(push_command)}", flush=True)
    pushed = subprocess.run(push_command, cwd=str(cwd), check=False)
    if pushed.returncode != 0:
        return fail("git push failed (see above).")

    print("✅ Pushed.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
