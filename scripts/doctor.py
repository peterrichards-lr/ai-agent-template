#!/usr/bin/env python3
"""
doctor.py - Post-Bootstrap Verification

Verifies that a repository bootstrapped from this template is actually finished:
no template placeholder survived the regex substitutions in bootstrap_template.py,
the .claude/skills auto-discovery symlink resolves to a directory, and the agent
scratchpad was seeded. Every finding is reported with its file and line, and the
process exits 1 so a silent miss becomes a loud failure.

Modes:
  adopter  (default) -- a bootstrapped project. Every placeholder anywhere is a
           failure and .agent-state.md must exist.
  template -- this template repository itself, where the adopter-facing stubs
           (AGENTS.md, CODE_OF_CONDUCT.md, ...) are *supposed* to still carry
           their placeholders and .agent-state.md is gitignored and absent from
           a fresh checkout. Everything else, README.md included, stays strict.
"""

import argparse
import os
import re
import sys
from collections import namedtuple
from pathlib import Path

# Allow importing sibling script helpers regardless of invocation working directory
sys.path.insert(0, str(Path(__file__).parent.resolve()))
from check_docs_review import IGNORE_DIRS

ADOPTER_MODE = 'adopter'
TEMPLATE_MODE = 'template'
MODES = (ADOPTER_MODE, TEMPLATE_MODE)

# Any `<SOMETHING_PLACEHOLDER>` token is caught structurally so a placeholder
# added later is covered without editing this list. The literals below have no
# such structure and must be enumerated.
PLACEHOLDER_TOKEN_PATTERN = re.compile(r'<[A-Z][A-Z0-9_]*_PLACEHOLDER>')
LITERAL_PLACEHOLDER_TOKENS = ('your-org', 'my-ai-project')

# Documented inventory, used in the CLI help text. The pattern above is the
# authority for the angle-bracket family.
KNOWN_PLACEHOLDER_TOKENS = (
    '<GITHUB_OWNER_PLACEHOLDER>',
    '<CONDUCT_EMAIL_PLACEHOLDER>',
    '<TEST_COMMAND_PLACEHOLDER>',
) + LITERAL_PLACEHOLDER_TOKENS

# Files that legitimately contain the tokens in every mode because they define,
# document or test them rather than being adopter-facing content. A trailing
# slash marks a directory prefix.
TOKEN_DEFINITION_PATHS = (
    'scripts/bootstrap_template.py',
    'scripts/doctor.py',
    'docs/TEMPLATE_GUIDE.md',
    'tests/',
    '.agents/templates/',
)

# Additionally exempt in template mode only: the un-bootstrapped stubs whose
# placeholders bootstrap_template.py is responsible for substituting.
UNBOOTSTRAPPED_STUB_PATHS = (
    'AGENTS.md',
    'CODE_OF_CONDUCT.md',
    'CHANGELOG.md',
    '.github/CODEOWNERS',
    '.github/ISSUE_TEMPLATE/config.yml',
)

# Per-user agent worktrees are gitignored working copies of the repository;
# scanning them would report another checkout's findings against this one.
EXCLUDED_DIRECTORY_PATHS = ('.claude/worktrees',)

# Anything larger is a build artefact or asset rather than a document or config.
MAX_SCAN_BYTES = 1_000_000

AGENT_STATE_RELPATH = '.agent-state.md'
CLAUDE_SKILLS_RELPATH = '.claude/skills'
SYMLINK_REMEDY = (
    "re-clone with `git clone -c core.symlinks=true` (or enable Windows Developer Mode) "
    "and re-run scripts/bootstrap_template.py"
)

Finding = namedtuple('Finding', ['path', 'line', 'detail'])

def is_exempt(rel_path: str, mode: str) -> bool:
    """Report whether a repository-relative path may legitimately carry placeholders."""
    exempt_paths = TOKEN_DEFINITION_PATHS
    if mode == TEMPLATE_MODE:
        exempt_paths = exempt_paths + UNBOOTSTRAPPED_STUB_PATHS

    for exempt_path in exempt_paths:
        if exempt_path.endswith('/'):
            if rel_path.startswith(exempt_path):
                return True
        elif rel_path == exempt_path:
            return True
    return False

def iter_scannable_files(root_dir: Path):
    """Yield every readable, non-symlinked file under root_dir worth scanning."""
    for dir_path, dir_names, file_names in os.walk(root_dir, followlinks=False):
        current_dir = Path(dir_path)
        rel_dir = current_dir.relative_to(root_dir).as_posix()

        keep_dirs = []
        for dir_name in sorted(dir_names):
            child = current_dir / dir_name
            rel_child = dir_name if rel_dir == '.' else f"{rel_dir}/{dir_name}"
            if dir_name in IGNORE_DIRS or rel_child in EXCLUDED_DIRECTORY_PATHS:
                continue
            # Never descend a symlinked directory: .claude/skills points back
            # into .agents/skills and would be scanned (and reported) twice.
            if child.is_symlink():
                continue
            keep_dirs.append(dir_name)
        dir_names[:] = keep_dirs

        for file_name in sorted(file_names):
            file_path = current_dir / file_name
            if file_path.is_symlink():
                continue
            yield file_path

def find_placeholders_in_text(text: str):
    """Return (line_number, token) for every placeholder occurrence in text."""
    occurrences = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in PLACEHOLDER_TOKEN_PATTERN.finditer(line):
            occurrences.append((line_number, match.group(0)))
        for token in LITERAL_PLACEHOLDER_TOKENS:
            if token in line:
                occurrences.append((line_number, token))
    return occurrences

def scan_placeholders(root_dir: Path, mode: str) -> list:
    """Report every surviving template placeholder outside the exempt paths."""
    findings = []
    for file_path in iter_scannable_files(root_dir):
        rel_path = file_path.relative_to(root_dir).as_posix()
        if is_exempt(rel_path, mode):
            continue

        try:
            if file_path.stat().st_size > MAX_SCAN_BYTES:
                continue
            text = file_path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            # Unreadable or binary: nothing a text placeholder could hide in.
            continue

        for line_number, token in find_placeholders_in_text(text):
            findings.append(Finding(
                rel_path,
                line_number,
                f"unresolved template placeholder '{token}'"
            ))
    return findings

def check_claude_skills_link(root_dir: Path) -> list:
    """Assert .claude/skills resolves to a directory, not a materialised text file."""
    skills_path = root_dir / '.claude' / 'skills'

    if skills_path.is_dir():
        return []

    if skills_path.is_symlink() or skills_path.exists():
        detail = (
            "exists but does not resolve to a directory -- git materialised the symlink "
            f"as a regular file, so agent skill discovery silently finds nothing; {SYMLINK_REMEDY}"
        )
    else:
        detail = f"is missing, so agent skill discovery silently finds nothing; {SYMLINK_REMEDY}"

    return [Finding(CLAUDE_SKILLS_RELPATH, None, detail)]

def check_agent_state_scratchpad(root_dir: Path) -> list:
    """Assert the gitignored agent scratchpad was seeded by bootstrap."""
    if (root_dir / AGENT_STATE_RELPATH).is_file():
        return []
    return [Finding(
        AGENT_STATE_RELPATH,
        None,
        "was never seeded; re-run scripts/bootstrap_template.py to copy it from "
        ".agents/templates/agent-state.md"
    )]

def run_doctor(root_dir: Path = None, mode: str = ADOPTER_MODE) -> list:
    """Return every verification finding for root_dir, sorted by file then line."""
    if mode not in MODES:
        raise ValueError(f"Unknown doctor mode '{mode}'. Expected one of: {', '.join(MODES)}")

    if root_dir is None:
        root_dir = Path(__file__).parent.parent
    root_dir = Path(root_dir).resolve()

    findings = scan_placeholders(root_dir, mode)
    findings.extend(check_claude_skills_link(root_dir))
    if mode == ADOPTER_MODE:
        findings.extend(check_agent_state_scratchpad(root_dir))

    return sorted(findings, key=lambda finding: (finding.path, finding.line or 0))

def format_findings(findings: list) -> str:
    """Render findings as one `path:line: detail` citation per line."""
    if not findings:
        return "Doctor: no unresolved template placeholders or structural problems found."

    lines = [f"Doctor found {len(findings)} unresolved template problem(s):"]
    for finding in findings:
        location = finding.path if finding.line is None else f"{finding.path}:{finding.line}"
        lines.append(f"  {location}: {finding.detail}")
    return "\n".join(lines)

def run_doctor_and_report(root_dir: Path = None, mode: str = ADOPTER_MODE) -> bool:
    """Run the doctor, print its report, and return True when the tree is clean."""
    findings = run_doctor(root_dir, mode)
    if findings:
        print(format_findings(findings), file=sys.stderr)
        return False
    print(format_findings(findings))
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Verify a bootstrapped repository has no surviving template placeholders.",
        epilog="Known placeholder tokens: " + ", ".join(KNOWN_PLACEHOLDER_TOKENS)
    )
    parser.add_argument('--dir', type=str, default=None, help='Repository root to verify')
    parser.add_argument(
        '--mode', choices=MODES, default=ADOPTER_MODE,
        help="'adopter' (default) for a bootstrapped project; 'template' for this template repository"
    )

    args = parser.parse_args()
    target_dir = Path(args.dir).resolve() if args.dir else None

    if not run_doctor_and_report(target_dir, mode=args.mode):
        sys.exit(1)

if __name__ == '__main__':
    main()
