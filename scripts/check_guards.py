#!/usr/bin/env python3
"""
check_guards.py - Blocking, zero-dependency guards for project invariants.

A guard is a regular expression that must never match in a set of files, plus the
reason it exists and what to do instead. Guards live in `.guards.json` and run as a
pre-commit hook, so they block locally and in CI from the moment they are added.

Guards and `.semgrep.yaml` are complementary, not alternatives:

- `.semgrep.yaml` is syntax-aware and runs (with third-party rule packs) in the
  non-blocking security scan, because a new rule there may arrive with a backlog of
  existing findings to triage.
- A guard is line-level and blocks immediately, because it is added *with the fix* that
  brought its match count to zero -- typically after a bug: "this class of mistake
  happened once; make the next occurrence fail the commit". There is no backlog to
  triage, so there is no reason to let it merely report.

Each guard in `.guards.json`:

  id       kebab-case, unique; names the banned thing.
  pattern  Python regular expression, matched against each line.
  include  glob list (fnmatch: `*` also crosses `/`) of repository paths to check.
  exclude  optional glob list carved out of `include` (e.g. the approved helper).
  why      the incident or rule this guard encodes -- required, so a finding teaches.
  instead  what to do instead -- required, for the same reason.

Files checked are git's tracked plus untracked-but-not-ignored files; `.guards.json`
itself is never checked, since it necessarily spells out every banned pattern.

Exit codes: 0 no findings; 1 findings; 2 `.guards.json` is invalid or git failed.
"""

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

GUARDS_RELPATH = '.guards.json'
REQUIRED_FIELDS = ('id', 'pattern', 'include', 'why', 'instead')


class GuardConfigError(Exception):
    """`.guards.json` cannot be parsed into a usable set of guards."""


@dataclass(frozen=True)
class Guard:
    id: str
    pattern: re.Pattern
    include: tuple
    exclude: tuple
    why: str
    instead: str

    def applies_to(self, relpath: str) -> bool:
        return (any(fnmatch.fnmatchcase(relpath, glob) for glob in self.include)
                and not any(fnmatch.fnmatchcase(relpath, glob) for glob in self.exclude))


def _glob_list(entry: dict, field: str, guard_id: str, required: bool) -> tuple:
    value = entry.get(field, None if required else [])
    if not isinstance(value, list) or not all(isinstance(g, str) and g for g in value):
        raise GuardConfigError(f"guard {guard_id!r}: {field!r} must be a list of glob strings")
    if required and not value:
        raise GuardConfigError(f"guard {guard_id!r}: {field!r} must not be empty")
    return tuple(value)


def load_guards(root_dir: Path) -> list:
    config_path = root_dir / GUARDS_RELPATH
    if not config_path.is_file():
        raise GuardConfigError(f"{GUARDS_RELPATH} not found")
    try:
        config = json.loads(config_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise GuardConfigError(f"{GUARDS_RELPATH} is not valid JSON: {error}") from error
    entries = config.get('guards') if isinstance(config, dict) else None
    if not isinstance(entries, list):
        raise GuardConfigError(f"{GUARDS_RELPATH} must be an object with a 'guards' list")

    guards, seen = [], set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise GuardConfigError(f"guards[{index}] must be an object")
        missing = [f for f in REQUIRED_FIELDS if not entry.get(f)]
        if missing:
            raise GuardConfigError(f"guards[{index}] is missing {', '.join(missing)}")
        guard_id = entry['id']
        if guard_id in seen:
            raise GuardConfigError(f"duplicate guard id {guard_id!r}")
        seen.add(guard_id)
        try:
            pattern = re.compile(entry['pattern'])
        except re.error as error:
            raise GuardConfigError(f"guard {guard_id!r}: invalid pattern: {error}") from error
        guards.append(Guard(
            id=guard_id,
            pattern=pattern,
            include=_glob_list(entry, 'include', guard_id, required=True),
            exclude=_glob_list(entry, 'exclude', guard_id, required=False),
            why=entry['why'],
            instead=entry['instead'],
        ))
    return guards


def candidate_files(root_dir: Path) -> list:
    try:
        output = subprocess.run(
            ['git', '-C', str(root_dir), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            check=True, capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise GuardConfigError(f"could not list repository files with git: {error}") from error
    paths = sorted({p for p in output.decode('utf-8').split('\0') if p})
    return [p for p in paths if p != GUARDS_RELPATH]


def scan(root_dir: Path, guards: list, relpaths: list) -> list:
    """Return (guard, relpath, line_number, line) for every match."""
    findings = []
    for relpath in relpaths:
        applicable = [g for g in guards if g.applies_to(relpath)]
        path = root_dir / relpath
        if not applicable or path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        if b'\0' in data:
            continue  # binary
        for line_number, line in enumerate(data.decode('utf-8', errors='replace').splitlines(), 1):
            for guard in applicable:
                if guard.pattern.search(line):
                    findings.append((guard, relpath, line_number, line.strip()))
    return findings


def run(root_dir: Path) -> int:
    try:
        guards = load_guards(root_dir)
        findings = scan(root_dir, guards, candidate_files(root_dir))
    except GuardConfigError as error:
        print(f"❌ Guards: {error}", file=sys.stderr)
        return 2

    if not findings:
        print(f"✓ {len(guards)} guard(s) passed.")
        return 0

    print(f"❌ {len(findings)} guard finding(s):", file=sys.stderr)
    for guard, relpath, line_number, line in findings:
        print(f"  {relpath}:{line_number}: [{guard.id}] {line}", file=sys.stderr)
    for guard in {g.id: g for g, *_ in findings}.values():
        print(f"\n  [{guard.id}]\n    why:     {guard.why}\n    instead: {guard.instead}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository root (default: this script's repository)")
    args = parser.parse_args(argv)
    return run(args.root.resolve())


if __name__ == '__main__':
    sys.exit(main())
