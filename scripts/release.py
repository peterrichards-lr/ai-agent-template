#!/usr/bin/env python3
"""
release.py - Semantic Release Preparation, Issue-Closure Audit & Tagging Gate

`.agents/skills/release-management/SKILL.md` sets a real policy -- semver, "a tag
without release notes is an unchecked gap", audit that every expected issue actually
closed, tagging is human-gated -- and `.github/rulesets/protect-version-tags.json`
makes `v*` tags immutable once pushed. That is a strict policy plus a rule that makes
mistakes permanent. This script is the tooling that executes it.

Git tags are the single source of version truth. There is deliberately no VERSION
file: five annotated tags already exist, `scripts/check_template_drift.py` already
reads `git describe --tags --abbrev=0` to stamp and compare template versions, and a
file would create a second source that can disagree with the tags the drift checker
reads. Go projects have no version file at all -- tags *are* the version -- so a
file-based scheme would need a per-stack exception on day one.

The highest-value part is the issue-closure audit. Rule 3 says to verify, not assume,
that every issue a batch was supposed to close actually closed. Done by hand across
a backlog of merged pull requests that is the step everyone skips, and a `Closes #N`
silently dropped by a squash-merge then goes unnoticed for another release cycle.
Here it is a gate: a referenced issue that is still open, or whose state cannot be
verified, refuses the release.

Three phases, deliberately separate, because tagging is irreversible:

  1. python3 scripts/release.py --dry-run     # audit + propose; touches nothing
  2. python3 scripts/release.py               # writes the CHANGELOG.md section
     git add CHANGELOG.md && git commit ...   # human reviews and commits the notes
  3. python3 scripts/release.py --tag         # confirms, then creates the annotated tag
     git push origin vX.Y.Z                   # human pushes; release.yml publishes

Phase 3 is separate from phase 2 on purpose: the tag must point at the commit that
*contains* the release notes, because `.github/workflows/release.yml` publishes the
GitHub Release from the changelog section found at the tagged commit. Tagging before
committing the notes would publish an empty release.

This script never pushes and never calls `gh release create`. Pushing the tag is the
human's action, and publishing is the workflow's.

Exit codes:
  0  the requested phase completed
  1  usage or environment error (not a git repository, unparseable tag, no changelog)
  2  refused: nothing to release, unconfirmed tagging, dirty tree, tag already exists
  3  the issue-closure audit failed -- nothing was written and nothing was tagged
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

# Allow importing sibling script helpers regardless of invocation working directory
sys.path.insert(0, str(Path(__file__).parent.resolve()))
# The closing-keyword vocabulary is already defined -- and already tested -- for the
# PR gate. Re-deriving it here would let the release audit and the PR check disagree
# about what "Closes #N" looks like.
from check_closing_refs import CLOSING_REF_REGEX

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2
EXIT_AUDIT_FAILED = 3

# `vMAJOR.MINOR.PATCH`, per release-management/SKILL.md rule 1. Pre-release and build
# metadata are rejected rather than silently accepted: this template has never shipped
# one, and `v1.5.0-rc1` sorts in ways the bump arithmetic below does not model.
VERSION_TAG_REGEX = re.compile(r'^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$')

# type(scope)!: description -- the Conventional Commits subject line.
CONVENTIONAL_SUBJECT_REGEX = re.compile(
    r'^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:[ \t]*(?P<description>.+)$')

# The `(#123)` a squash-merge appends to the subject. Anchored at the end so a `(#12)`
# occurring mid-sentence is not mistaken for the pull request number.
PULL_REQUEST_SUFFIX_REGEX = re.compile(r'\s*\(#(?P<number>\d+)\)\s*$')

# `BREAKING CHANGE:` (and the hyphenated spelling git users actually type) in a footer.
BREAKING_CHANGE_REGEX = re.compile(r'^BREAKING[ -]CHANGE\s*:', re.MULTILINE)

# A parenthesised closing reference left in the subject, e.g. #76's real subject:
# "feat(ci): add PR scope-sprawl CI gate ... (Closes #52) (#76)". It belongs in the
# audit, not in the rendered description.
INLINE_CLOSING_REF_REGEX = re.compile(
    r'\s*\(?\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b\s*:?\s*#\d+\)?', re.IGNORECASE)

# The synthetic baseline for a repository that has never been tagged. An adopter's
# first release starts from here and lands on v0.1.0 or v1.0.0 depending on --bump.
INITIAL_VERSION = 'v0.0.0'

BUMP_LEVELS = ('major', 'minor', 'patch')

# Conventional Commit type -> Keep a Changelog category. Everything unmapped is a
# Changed: a `docs:`, `ci:` or `chore:` commit changed the project without adding or
# fixing anything an adopter calls a feature or a bug.
CHANGELOG_CATEGORY_BY_TYPE = {
    'feat': 'Added',
    'fix': 'Fixed',
    'revert': 'Removed',
    'perf': 'Changed',
    'refactor': 'Changed',
    'docs': 'Changed',
    'build': 'Changed',
    'ci': 'Changed',
    'chore': 'Changed',
    'style': 'Changed',
    'test': 'Changed',
}
DEFAULT_CHANGELOG_CATEGORY = 'Changed'

# A `security` scope is the one signal strong enough to override the type mapping:
# `feat(security): pin GitHub Actions to commit SHAs` is what Keep a Changelog means
# by Security, and burying it under Added is what an adopter scanning for exposure
# would miss.
SECURITY_SCOPE = 'security'

# Keep a Changelog's fixed ordering. Categories with no entries are omitted.
CHANGELOG_CATEGORY_ORDER = ('Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security')

CHANGELOG_RELPATH = Path('CHANGELOG.md')
UNRELEASED_HEADING_REGEX = re.compile(r'^##[ \t]*\[Unreleased\][ \t]*$', re.MULTILINE)
VERSION_HEADING_REGEX_TEMPLATE = r'^##[ \t]*\[{version}\][^\n]*$'
# Where the [Unreleased] body stops: the next level-2 heading, an HTML comment block,
# a link reference definition, or the documentation footer rule.
UNRELEASED_BODY_TERMINATOR_REGEX = re.compile(r'^(?:##[ \t]|<!--|\[[^\]]+\]:|---[ \t]*$)')
UNRELEASED_LINK_REGEX = re.compile(
    r'^\[Unreleased\]:[ \t]*(?P<base>\S+?)/compare/(?P<from>\S+?)\.\.\.(?P<to>\S+)[ \t]*$',
    re.MULTILINE)
CATEGORY_HEADING_REGEX = re.compile(r'^###[ \t]+(?P<category>.+?)[ \t]*$', re.MULTILINE)
NOTHING_YET_PLACEHOLDER = '_Nothing yet._'

# Git and gh subcommands are cheap; a hung network call is not. Bound every one.
DEFAULT_TIMEOUT_SECONDS = 60


class ReleaseError(Exception):
    """Raised when the release cannot be computed from the repository's own state."""


class CommitEntry(NamedTuple):
    """One commit in the release range, parsed as far as it can be parsed.

    A commit that is not a Conventional Commit -- a Dependabot merge commit, say --
    is kept rather than dropped: it still counts towards "is there anything to
    release", and its closing references still belong in the audit. It is simply not
    rendered into the notes, because there is no reliable way to categorise it.
    """

    sha: str
    subject: str
    body: str
    type: str
    scope: str
    breaking: bool
    description: str
    pull_request: Optional[int]
    issues: Tuple[int, ...]

    @property
    def is_conventional(self) -> bool:
        return bool(self.type)

    @property
    def references(self) -> Tuple[int, ...]:
        """Every issue/PR number this commit is identified by, PR first."""
        numbers = ([self.pull_request] if self.pull_request else []) + list(self.issues)
        seen, ordered = set(), []
        for number in numbers:
            if number not in seen:
                seen.add(number)
                ordered.append(number)
        return tuple(ordered)


class IssueAudit(NamedTuple):
    """The result of checking that every referenced issue actually closed."""

    closed: Tuple[int, ...]
    open_issues: Tuple[int, ...]
    unverified: Tuple[int, ...]
    skipped: bool

    @property
    def ok(self) -> bool:
        """False on any mismatch. An unverifiable state is a mismatch, not a pass.

        release-management/SKILL.md rule 3 and rule-adherence/SKILL.md agree on this:
        verify, don't assume. "gh was not installed" is not evidence that the issues
        closed, so it fails closed. --skip-issue-audit is the loud, recorded opt-out.
        """
        if self.skipped:
            return True
        return not self.open_issues and not self.unverified


def run_command(arguments: Sequence[str], cwd: Optional[Path] = None,
                timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Tuple[int, str, str]:
    """Run a subprocess non-interactively, never prompting and never hanging.

    Returns (returncode, stdout, stderr). A missing binary, a timeout or an OS error
    is reported as a non-zero return code rather than raised: every caller has a
    meaningful degraded path, and a release helper that raises a traceback because
    `gh` is not installed is a release helper nobody runs twice.
    """
    environment = dict(os.environ)
    # A credential prompt inside a release script would block a terminal forever.
    environment['GIT_TERMINAL_PROMPT'] = '0'
    environment['GIT_ASKPASS'] = 'echo'

    try:
        completed = subprocess.run(
            list(arguments), cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, check=False,
            env=environment, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 1, '', f"{arguments[0]} timed out after {timeout}s"
    except (OSError, FileNotFoundError) as error:
        return 1, '', f"{arguments[0]} is unavailable: {error}"

    return completed.returncode, completed.stdout, completed.stderr


def run_git(root_dir: Path, arguments: Sequence[str],
            timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Tuple[int, str, str]:
    """Run a git subcommand against `root_dir`."""
    return run_command(['git', '-C', str(root_dir)] + list(arguments), timeout=timeout)


# ---------------------------------------------------------------------------
# Semantic version arithmetic
# ---------------------------------------------------------------------------

def parse_version_tag(tag: str) -> Tuple[int, int, int]:
    """Parse `v1.4.0` (or `1.4.0`) into its numeric components."""
    match = VERSION_TAG_REGEX.match((tag or '').strip())
    if not match:
        raise ReleaseError(
            f"'{tag}' is not a vMAJOR.MINOR.PATCH tag. release-management/SKILL.md "
            "rule 1 requires that form; pre-release and build metadata are not supported.")
    return int(match.group('major')), int(match.group('minor')), int(match.group('patch'))


def format_version_tag(version: Tuple[int, int, int]) -> str:
    """Render numeric components back into the repository's tag format."""
    return 'v{}.{}.{}'.format(*version)


def bump_version(tag: str, level: str) -> str:
    """Apply one semver bump, resetting the lower components as semver requires."""
    major, minor, patch = parse_version_tag(tag)

    if level == 'major':
        return format_version_tag((major + 1, 0, 0))
    if level == 'minor':
        return format_version_tag((major, minor + 1, 0))
    if level == 'patch':
        return format_version_tag((major, minor, patch + 1))

    raise ReleaseError(f"Unknown bump level '{level}'. Expected one of: {', '.join(BUMP_LEVELS)}.")


# ---------------------------------------------------------------------------
# Conventional Commit parsing
# ---------------------------------------------------------------------------

def _collect_closing_references(text: str) -> List[int]:
    """Return every issue number reached by a GitHub closing keyword in `text`."""
    numbers = []
    for keyword_match in CLOSING_REF_REGEX.finditer(text or ''):
        number = keyword_match.group(2) or keyword_match.group(3)
        if number:
            numbers.append(int(number))
    return numbers


def parse_commit(sha: str, subject: str, body: str = '') -> CommitEntry:
    """Parse one commit into the fields the notes and the audit need."""
    subject = (subject or '').strip()
    body = body or ''

    pull_request = None
    pull_request_match = PULL_REQUEST_SUFFIX_REGEX.search(subject)
    remainder = subject
    if pull_request_match:
        pull_request = int(pull_request_match.group('number'))
        remainder = subject[:pull_request_match.start()]

    issues = _collect_closing_references(subject) + _collect_closing_references(body)
    deduplicated_issues = tuple(sorted(set(issues)))

    conventional = CONVENTIONAL_SUBJECT_REGEX.match(remainder)
    if not conventional:
        return CommitEntry(sha=sha, subject=subject, body=body, type='', scope='',
                           breaking=False, description=remainder.strip(),
                           pull_request=pull_request, issues=deduplicated_issues)

    description = INLINE_CLOSING_REF_REGEX.sub('', conventional.group('description')).strip()

    return CommitEntry(
        sha=sha,
        subject=subject,
        body=body,
        type=conventional.group('type').lower(),
        scope=(conventional.group('scope') or '').strip(),
        breaking=bool(conventional.group('breaking')) or bool(BREAKING_CHANGE_REGEX.search(body)),
        description=description,
        pull_request=pull_request,
        issues=deduplicated_issues,
    )


def read_commits(root_dir: Path, revision_range: str,
                 timeout: int = DEFAULT_TIMEOUT_SECONDS) -> List[CommitEntry]:
    """Read and parse every non-merge commit in `revision_range`.

    `--no-merges` because this repository squash-merges: a Dependabot merge commit and
    the commit it merged describe the same change, and counting both would render the
    entry twice and double-count its closing references.

    Unit separator / record separator delimiters rather than newlines: commit bodies
    contain blank lines, bullet lists and code fences, and any newline-delimited format
    would mis-split the very commits whose bodies carry the `Closes #N` footers.
    """
    code, output, stderr = run_git(
        root_dir, ['log', '--no-merges', '--format=%H%x1f%s%x1f%b%x1e', revision_range],
        timeout=timeout)
    if code != 0:
        raise ReleaseError(f"git log {revision_range} failed: {stderr.strip()}")

    commits = []
    for record in output.split('\x1e'):
        record = record.strip('\n')
        if not record.strip():
            continue
        parts = record.split('\x1f')
        if len(parts) < 2:
            continue
        sha, subject = parts[0], parts[1]
        body = parts[2] if len(parts) > 2 else ''
        commits.append(parse_commit(sha.strip(), subject, body))

    return commits


def classify_bump(commits: Sequence[CommitEntry]) -> Tuple[str, str]:
    """Propose a semver level from the commits, and explain the proposal.

    Propose, never assume: the returned reason is printed so a human can disagree and
    pass --bump. Anything that is not a `feat` or a breaking change lands on patch,
    including the non-conventional commits -- a range that changed *something* is not
    a no-op release, and under-proposing is the safe direction because the human sees
    the reason and can raise it.
    """
    if not commits:
        raise ReleaseError('Refusing to classify an empty commit range.')

    breaking = [c for c in commits if c.breaking]
    if breaking:
        return 'major', (f"{len(breaking)} breaking change(s): "
                         + ', '.join(sorted({c.scope or c.type or c.sha[:7] for c in breaking})))

    features = [c for c in commits if c.type == 'feat']
    if features:
        return 'minor', f"{len(features)} feat commit(s) and no breaking change"

    fixes = [c for c in commits if c.type == 'fix']
    if fixes:
        return 'patch', f"{len(fixes)} fix commit(s), no feat and no breaking change"

    return 'patch', f"{len(commits)} commit(s), none of them feat, fix or breaking"


# ---------------------------------------------------------------------------
# The issue-closure audit (release-management/SKILL.md rule 3)
# ---------------------------------------------------------------------------

def collect_referenced_issues(commits: Sequence[CommitEntry]) -> Tuple[int, ...]:
    """Every issue number a commit in the range claimed to close, deduplicated."""
    numbers = {number for commit in commits for number in commit.issues}
    return tuple(sorted(numbers))


def audit_issue_closures(issue_numbers: Sequence[int],
                         lookup: Callable[[int], Optional[str]],
                         skipped: bool = False) -> IssueAudit:
    """Check every referenced issue really is closed.

    `lookup` returns the issue state ('OPEN' / 'CLOSED') or None when the state could
    not be determined. Injected rather than called directly so the gate is testable
    without a network, and so an offline run degrades into an explicit refusal rather
    than a silent pass.
    """
    if skipped:
        return IssueAudit(closed=(), open_issues=(), unverified=(), skipped=True)

    closed, still_open, unverified = [], [], []
    for number in issue_numbers:
        state = lookup(number)
        if state is None:
            unverified.append(number)
        elif state.upper() == 'CLOSED':
            closed.append(number)
        else:
            still_open.append(number)

    return IssueAudit(closed=tuple(closed), open_issues=tuple(still_open),
                      unverified=tuple(unverified), skipped=False)


def make_gh_issue_lookup(repo: Optional[str] = None,
                         timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Callable[[int], Optional[str]]:
    """Build a lookup that asks `gh` for one issue's state.

    One call per issue rather than a single list query: a release range can reference
    an issue that was transferred, deleted, or belongs to another repository, and a
    per-issue answer attributes the failure to the number that caused it instead of
    reporting "some issue is missing".
    """
    import json

    def lookup(number: int) -> Optional[str]:
        arguments = ['gh', 'issue', 'view', str(number), '--json', 'number,state,title']
        if repo:
            arguments += ['--repo', repo]

        code, output, _ = run_command(arguments, timeout=timeout)
        if code != 0:
            return None
        try:
            return str(json.loads(output).get('state') or '') or None
        except (ValueError, AttributeError):
            return None

    return lookup


# ---------------------------------------------------------------------------
# Changelog rendering
# ---------------------------------------------------------------------------

def changelog_category(commit: CommitEntry) -> str:
    """Map one commit onto its Keep a Changelog category."""
    if commit.scope.lower() == SECURITY_SCOPE:
        return 'Security'
    return CHANGELOG_CATEGORY_BY_TYPE.get(commit.type, DEFAULT_CHANGELOG_CATEGORY)


def render_commit_entry(commit: CommitEntry) -> str:
    """Render one commit as a changelog bullet, linking its pull request and issues.

    Numbers are rendered bare (`(#93, #40)`) rather than with a closing keyword. A
    `Closes #40` written into a tracked file is harmless today, but the same text
    pasted into a pull request body is exactly what scripts/check_closing_refs.py
    exists to reject, and changelog entries get pasted into pull request bodies.
    """
    prefix = '**Breaking**: ' if commit.breaking else ''
    scope = f"**{commit.scope}**: " if commit.scope else ''
    references = commit.references
    suffix = f" ({', '.join('#' + str(number) for number in references)})" if references else ''
    return f"- {prefix}{scope}{commit.description}{suffix}"


def group_commits_by_category(commits: Sequence[CommitEntry]) -> Dict[str, List[CommitEntry]]:
    """Bucket the conventional commits by Keep a Changelog category, in order."""
    grouped: Dict[str, List[CommitEntry]] = {}
    for commit in commits:
        if not commit.is_conventional:
            continue
        grouped.setdefault(changelog_category(commit), []).append(commit)
    return grouped


def generate_category_lines(commits: Sequence[CommitEntry],
                            already_covered: Sequence[int] = ()) -> Dict[str, List[str]]:
    """Render the commits into {category: [bullet lines]}.

    `already_covered` holds issue/PR numbers a human already described by hand under
    `[Unreleased]`. Their commits are skipped: the hand-written entry says what changed
    and *why it matters*, which is what rule 2 asks for and what a generated line
    derived from a commit subject cannot.
    """
    covered = set(already_covered)
    selected = [commit for commit in commits
                if not (covered and covered.intersection(commit.references))]

    return {category: [render_commit_entry(commit) for commit in entries]
            for category, entries in group_commits_by_category(selected).items()}


def render_category_blocks(lines_by_category: Dict[str, List[str]]) -> str:
    """Render {category: lines} as Keep a Changelog `### Category` blocks, in order.

    One heading per category, whether its bullets were written by a human or generated
    here. Emitting a curated block and a generated block separately produced two
    `### Added` headings in the same release section -- valid Markdown, wrong document,
    and invisible to markdownlint because MD024 is disabled in .markdownlint-cli2.jsonc.
    """
    ordered = list(CHANGELOG_CATEGORY_ORDER)
    # A category a human invented (Keep a Changelog says to use the six, but the file
    # is theirs) keeps its entries rather than being silently dropped.
    ordered += [category for category in lines_by_category if category not in ordered]

    blocks = []
    for category in ordered:
        lines = lines_by_category.get(category)
        if not lines:
            continue
        blocks.append(f"### {category}\n\n" + '\n'.join(lines))

    return '\n\n'.join(blocks)


def render_changelog_entries(commits: Sequence[CommitEntry],
                             already_covered: Sequence[int] = ()) -> str:
    """Render a release section's categorised bullet list from commits alone."""
    return render_category_blocks(generate_category_lines(commits, already_covered))


def _split_unreleased(content: str) -> Tuple[str, str, str]:
    """Split a changelog into (before, [Unreleased] body, after)."""
    heading = UNRELEASED_HEADING_REGEX.search(content)
    if not heading:
        raise ReleaseError(
            'CHANGELOG.md has no "## [Unreleased]" heading. Keep a Changelog format is '
            'required: the release section is inserted directly below it.')

    body_start = heading.end()
    lines = content[body_start:].splitlines(keepends=True)

    offset = 0
    for line in lines:
        if UNRELEASED_BODY_TERMINATOR_REGEX.match(line):
            break
        offset += len(line)

    return content[:body_start], content[body_start:body_start + offset], content[body_start + offset:]


def _referenced_numbers(text: str) -> List[int]:
    """Every `#N` reference appearing in a block of prose."""
    return [int(number) for number in re.findall(r'#(\d+)', text)]


def curated_category_lines(unreleased_body: str) -> Dict[str, List[str]]:
    """The hand-written [Unreleased] content as {category: lines}.

    Continuation lines of a wrapped bullet are kept as-is, so a multi-line curated
    entry survives the move into the version section unchanged. `_Nothing yet._`
    placeholders are dropped: they are the empty state, not content.
    """
    matches = list(CATEGORY_HEADING_REGEX.finditer(unreleased_body))
    if not matches:
        stripped = unreleased_body.strip()
        if stripped in ('', NOTHING_YET_PLACEHOLDER):
            return {}
        # An [Unreleased] block with entries but no category headings: keep the prose
        # under the Keep a Changelog default rather than discarding a human's writing.
        return {DEFAULT_CHANGELOG_CATEGORY: stripped.splitlines()}

    curated: Dict[str, List[str]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(unreleased_body)
        entries = [line for line in unreleased_body[match.end():end].splitlines()
                   if line.strip() and NOTHING_YET_PLACEHOLDER not in line]
        if entries:
            curated.setdefault(match.group('category'), []).extend(entries)

    return curated


def apply_changelog_release(content: str, version: str, release_date: str,
                            commits: Sequence[CommitEntry]) -> str:
    """Promote [Unreleased] into a dated version section and add the generated notes.

    Curated entries move down verbatim -- deleting a human's explanation of why a
    change matters in favour of a restated commit subject would be a downgrade. The
    generated entries then fill in everything the human did not already cover, merged
    into the same `### Category` heading rather than repeating it.
    """
    before, unreleased_body, after = _split_unreleased(content)

    curated = curated_category_lines(unreleased_body)
    covered = _referenced_numbers('\n'.join(
        line for lines in curated.values() for line in lines))

    merged = {category: list(lines) for category, lines in curated.items()}
    for category, lines in generate_category_lines(commits, already_covered=covered).items():
        merged.setdefault(category, []).extend(lines)

    section_body = render_category_blocks(merged)
    if not section_body.strip():
        section_body = f"- {NOTHING_YET_PLACEHOLDER}"

    numeric_version = version.lstrip('v')
    # Trailing blank line, not just a newline: whatever follows [Unreleased] in the
    # file -- the commented example block, the link definitions, the documentation
    # footer -- must not end up glued to the last bullet, where a Markdown parser can
    # read it as a continuation of that list item.
    section = f"\n## [{numeric_version}] - {release_date}\n\n{section_body}\n\n"

    reset_unreleased = f"\n\n{NOTHING_YET_PLACEHOLDER}\n"

    return _rewrite_link_definitions(
        before + reset_unreleased + section + after, version)


def _rewrite_link_definitions(content: str, version: str) -> str:
    """Point [Unreleased] at the new tag and add this version's release link.

    The base URL is read out of the existing `[Unreleased]:` definition rather than
    constructed, so the un-bootstrapped template's owner placeholder survives untouched
    and an adopter's real owner is preserved without this script having to know either.
    """
    match = UNRELEASED_LINK_REGEX.search(content)
    if not match:
        return content

    base = match.group('base')
    numeric_version = version.lstrip('v')
    new_unreleased = f"[Unreleased]: {base}/compare/{version}...HEAD"
    version_link = f"[{numeric_version}]: {base}/releases/tag/{version}"

    updated = content[:match.start()] + new_unreleased + content[match.end():]
    if version_link not in updated:
        updated = updated.replace(new_unreleased, f"{new_unreleased}\n{version_link}", 1)
    return updated


def extract_changelog_section(content: str, version: str) -> str:
    """Return the body of one version's changelog section.

    `.github/workflows/release.yml` publishes exactly this text as the GitHub Release
    body, so the parsing lives here where tests/test_release.py covers it rather than
    in workflow shell where nothing does.
    """
    numeric_version = re.escape(version.lstrip('v'))
    heading = re.compile(VERSION_HEADING_REGEX_TEMPLATE.format(version=numeric_version),
                         re.MULTILINE).search(content)
    if not heading:
        raise ReleaseError(
            f"CHANGELOG.md has no section for {version}. Run "
            "`python3 scripts/release.py` to write one before tagging.")

    remainder = content[heading.end():]
    next_heading = re.search(r'^##[ \t]', remainder, re.MULTILINE)
    section = remainder[:next_heading.start()] if next_heading else remainder

    # A trailing documentation footer or link-definition block belongs to the file,
    # not to this release.
    section = re.split(r'^(?:<!--|\[[^\]]+\]:|---[ \t]*$)', section, maxsplit=1,
                       flags=re.MULTILINE)[0]
    return section.strip()


# ---------------------------------------------------------------------------
# Repository state
# ---------------------------------------------------------------------------

def current_version_tag(root_dir: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Optional[str]:
    """The most recent annotated tag, or None for a repository that has never tagged."""
    code, output, _ = run_git(root_dir, ['describe', '--tags', '--abbrev=0'], timeout=timeout)
    return output.strip() if code == 0 and output.strip() else None


def working_tree_is_clean(root_dir: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bool:
    """True when nothing is staged, modified or untracked."""
    code, output, _ = run_git(root_dir, ['status', '--porcelain'], timeout=timeout)
    return code == 0 and not output.strip()


def tag_exists(root_dir: Path, tag: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bool:
    code, _, _ = run_git(root_dir, ['rev-parse', '--verify', f'refs/tags/{tag}'], timeout=timeout)
    return code == 0


def confirm_tagging(version: str, assume_yes: bool) -> bool:
    """Gate the one irreversible action behind an explicit human answer.

    human-in-the-loop/SKILL.md puts tagging alongside merging, and
    protect-version-tags.json makes a pushed `v*` tag impossible to delete or move.
    With no TTY and no --yes this refuses rather than proceeding: a release script
    that tags by default inside CI is precisely the failure the ruleset cannot undo.
    """
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("\n✗ Refusing to tag non-interactively. Re-run with --yes once you have "
              "reviewed the notes above.", file=sys.stderr)
        return False
    try:
        answer = input(f"\nCreate the annotated tag {version} at HEAD? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in ('y', 'yes')


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_commits(commits: Sequence[CommitEntry], revision_range: str, limit: int = 40) -> None:
    """Summarise the range, truncating the commit list rather than the counts.

    A first run against a long-neglected backlog is the expected case, not the
    exception -- this repository sat 35 commits past its own last tag -- so the summary
    has to stay readable at that size.
    """
    conventional = [c for c in commits if c.is_conventional]
    print(f"Range    : {revision_range}")
    print(f"Commits  : {len(commits)} ({len(conventional)} conventional, "
          f"{len(commits) - len(conventional)} unclassified)")

    unclassified = [c for c in commits if not c.is_conventional]
    if unclassified:
        print(f"\n⚠️ {len(unclassified)} commit(s) are not Conventional Commits and will not "
              "appear in the notes:")
        for commit in unclassified[:limit]:
            print(f"  - {commit.sha[:7]} {commit.subject}")
        if len(unclassified) > limit:
            print(f"  ... and {len(unclassified) - limit} more")


def report_audit(audit: IssueAudit, issue_numbers: Sequence[int]) -> None:
    """Print the issue-closure audit result."""
    if audit.skipped:
        print(f"\n⚠️ Issue-closure audit SKIPPED (--skip-issue-audit). "
              f"{len(issue_numbers)} referenced issue(s) were not verified.")
        return

    if not issue_numbers:
        print("\nIssue audit: no closing references in this range -- nothing to verify.")
        return

    print(f"\nIssue audit: {len(issue_numbers)} referenced issue(s)")
    if audit.closed:
        print(f"  ✓ closed     : {', '.join('#' + str(n) for n in audit.closed)}")
    if audit.open_issues:
        print(f"  ✗ still open : {', '.join('#' + str(n) for n in audit.open_issues)}")
    if audit.unverified:
        print(f"  ✗ unverified : {', '.join('#' + str(n) for n in audit.unverified)}")


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

def run_release(root_dir: Path, bump: Optional[str] = None, dry_run: bool = False,
                create_tag: bool = False, assume_yes: bool = False,
                skip_issue_audit: bool = False, repo: Optional[str] = None,
                release_date: Optional[str] = None,
                timeout: int = DEFAULT_TIMEOUT_SECONDS) -> int:
    """Run one release phase and return the process exit code."""
    changelog_path = root_dir / CHANGELOG_RELPATH
    if not changelog_path.exists():
        print(f"❌ {CHANGELOG_RELPATH.as_posix()} not found in {root_dir}.", file=sys.stderr)
        return EXIT_ERROR

    previous_tag = current_version_tag(root_dir, timeout=timeout)
    if previous_tag is None:
        print("⚠️ No version tag found; treating this as the first release.")
        base_version = INITIAL_VERSION
        revision_range = 'HEAD'
    else:
        base_version = previous_tag
        revision_range = f'{previous_tag}..HEAD'

    try:
        commits = read_commits(root_dir, revision_range, timeout=timeout)
    except ReleaseError as error:
        print(f"❌ {error}", file=sys.stderr)
        return EXIT_ERROR

    if not commits:
        print(f"✗ Nothing to release: no commits in {revision_range}.", file=sys.stderr)
        return EXIT_REFUSED

    try:
        if bump:
            level, reason = bump, 'requested with --bump'
        else:
            level, reason = classify_bump(commits)
        next_version = bump_version(base_version, level)
    except ReleaseError as error:
        print(f"❌ {error}", file=sys.stderr)
        return EXIT_ERROR

    print(f"Current  : {base_version}"
          + ('' if previous_tag else '  (synthetic: no tags in this repository)'))
    print(f"Proposed : {next_version}  ({level} -- {reason})")
    report_commits(commits, revision_range)

    issue_numbers = collect_referenced_issues(commits)
    audit = audit_issue_closures(
        issue_numbers,
        make_gh_issue_lookup(repo=repo, timeout=timeout),
        skipped=skip_issue_audit,
    )
    report_audit(audit, issue_numbers)

    changelog_text = changelog_path.read_text(encoding='utf-8')
    effective_date = release_date or datetime.today().strftime('%Y-%m-%d')
    updated_changelog = None

    if create_tag:
        # The notes were written and committed in the previous phase, so show what is
        # actually there. Re-applying apply_changelog_release() here would preview a
        # second, near-empty section -- everything already promoted into the committed
        # one is no longer under [Unreleased] to promote again.
        try:
            preview = extract_changelog_section(changelog_text, next_version)
        except ReleaseError:
            preview = ''  # _tag_phase reports the missing section precisely.
    else:
        try:
            updated_changelog = apply_changelog_release(
                changelog_text, next_version, effective_date, commits)
            preview = extract_changelog_section(updated_changelog, next_version)
        except ReleaseError as error:
            print(f"❌ {error}", file=sys.stderr)
            return EXIT_ERROR

    if preview:
        print(f"\n--- Draft notes for {next_version} ---\n")
        print(preview)
        print()

    if not audit.ok:
        print("\n✗ Issue-closure audit failed. Nothing was written and nothing was tagged.\n"
              "  release-management/SKILL.md rule 3: verify -- don't assume -- that every\n"
              "  issue this batch was supposed to close actually closed. Close the issues\n"
              "  above (a squash-merge may have dropped a 'Closes #N'), or re-run with\n"
              "  --skip-issue-audit if you have verified them another way.", file=sys.stderr)
        return EXIT_AUDIT_FAILED

    if dry_run:
        print("--dry-run: nothing was written, nothing was tagged.")
        return EXIT_OK

    if create_tag:
        # Flush first: _tag_phase's refusals go to stderr, and an unflushed stdout
        # would print the report *after* the reason it was rejected.
        sys.stdout.flush()
        return _tag_phase(root_dir, changelog_text, next_version, assume_yes, timeout)

    changelog_path.write_text(updated_changelog, encoding='utf-8')
    print(f"✓ Wrote the {next_version} section into {CHANGELOG_RELPATH.as_posix()}.\n\n"
          "Next:\n"
          f"  1. Review and edit {CHANGELOG_RELPATH.as_posix()} -- say what changed and why\n"
          "     it matters, not just what the commit subjects said.\n"
          f"  2. git add {CHANGELOG_RELPATH.as_posix()} && "
          f"git commit -m \"docs(release): prepare {next_version}\"\n"
          "  3. python3 scripts/release.py --tag\n")
    return EXIT_OK


def _tag_phase(root_dir: Path, changelog_text: str, version: str,
               assume_yes: bool, timeout: int) -> int:
    """Verify the preconditions, confirm, then create the annotated tag."""
    if tag_exists(root_dir, version, timeout=timeout):
        print(f"✗ Tag {version} already exists. Version tags are immutable "
              "(.github/rulesets/protect-version-tags.json): supersede it with a new "
              "version rather than moving it.", file=sys.stderr)
        return EXIT_REFUSED

    if not working_tree_is_clean(root_dir, timeout=timeout):
        print("✗ The working tree is not clean. Commit the release notes first, so the "
              "tag points at a commit that actually contains them -- "
              ".github/workflows/release.yml publishes the changelog section found at "
              "the tagged commit.", file=sys.stderr)
        return EXIT_REFUSED

    try:
        section = extract_changelog_section(changelog_text, version)
    except ReleaseError as error:
        print(f"✗ {error}", file=sys.stderr)
        return EXIT_REFUSED

    if not confirm_tagging(version, assume_yes):
        print("✗ Tagging declined. Nothing was changed.", file=sys.stderr)
        return EXIT_REFUSED

    code, _, stderr = run_git(
        root_dir, ['tag', '-a', version, '-m', f"{version}\n\n{section}\n"], timeout=timeout)
    if code != 0:
        print(f"❌ git tag failed: {stderr.strip()}", file=sys.stderr)
        return EXIT_ERROR

    print(f"✓ Created the annotated tag {version} at HEAD.\n\n"
          "This script does not push. Push it yourself once you are sure -- the tag "
          "becomes immutable:\n\n"
          f"    git push origin {version}\n\n"
          ".github/workflows/release.yml then publishes the GitHub Release from the "
          f"{version} changelog section.")
    return EXIT_OK


def run_extract_notes(root_dir: Path, version: str) -> int:
    """Print one version's changelog section on stdout, for release.yml to publish."""
    changelog_path = root_dir / CHANGELOG_RELPATH
    if not changelog_path.exists():
        print(f"❌ {CHANGELOG_RELPATH.as_posix()} not found in {root_dir}.", file=sys.stderr)
        return EXIT_ERROR

    try:
        print(extract_changelog_section(
            changelog_path.read_text(encoding='utf-8'), version))
    except ReleaseError as error:
        print(f"❌ {error}", file=sys.stderr)
        return EXIT_ERROR

    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description='Prepare a semantic release: audit issue closure, draft the '
                    'changelog notes, and gate the annotated tag behind confirmation.')
    parser.add_argument('--root', default=None,
                        help='Repository root (default: the repository containing this script)')
    parser.add_argument('--bump', choices=BUMP_LEVELS, default=None,
                        help='Override the semver level computed from the commit range')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the audit and the draft notes; write nothing, tag nothing')
    parser.add_argument('--tag', action='store_true',
                        help='Create the annotated tag (requires a clean tree and committed notes)')
    parser.add_argument('--yes', action='store_true',
                        help='Confirm tagging without a prompt. Required with --tag when no TTY.')
    parser.add_argument('--skip-issue-audit', action='store_true',
                        help='Skip the issue-closure audit (recorded loudly in the output)')
    parser.add_argument('--repo', default=None,
                        help='owner/name to audit issues against (default: the gh-detected repo)')
    parser.add_argument('--extract-notes', metavar='TAG', default=None,
                        help="Print a version's changelog section on stdout and exit")
    parser.add_argument('--release-date', default=None,
                        help='Date for the changelog heading (default: today, YYYY-MM-DD)')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT_SECONDS,
                        help='Per-subprocess timeout in seconds')

    args = parser.parse_args(argv)
    root_dir = Path(args.root).resolve() if args.root else Path(__file__).parent.parent.resolve()

    if args.extract_notes:
        return run_extract_notes(root_dir, args.extract_notes)

    return run_release(
        root_dir=root_dir,
        bump=args.bump,
        dry_run=args.dry_run,
        create_tag=args.tag,
        assume_yes=args.yes,
        skip_issue_audit=args.skip_issue_audit,
        repo=args.repo,
        release_date=args.release_date,
        timeout=args.timeout,
    )


if __name__ == '__main__':
    sys.exit(main())
