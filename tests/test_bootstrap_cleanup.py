"""
test_bootstrap_cleanup.py - Bootstrap Mutation Safety & Scaffolding Cleanup Suite

Covers the bootstrap behaviours that must not fail silently:
- the seeded .agent-state.md footer is rewritten to the bootstrap date (#80),
- regex substitutions that match nothing abort instead of warning (#56),
- --dry-run previews every mutation without touching the working tree (#56),
- --clean-template scrubs the template's Python-only scaffolding (#55),
- --clean-template resets CHANGELOG.md so no template release history is inherited (#105),
- SECURITY.md is seeded with the adopter's project name and reporting contact (#107),
- no delivered document cites a path the same --clean-template run removed (#109).
"""

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add scripts directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import bootstrap_template
from bootstrap_template import (
    AGENT_STATE_SEED_RELPATH,
    CONDUCT_EMAIL_PLACEHOLDER,
    DOCS_SITE_SCAFFOLD_RELPATHS,
    DOCTOR_ADOPTER_MODE_ENTRY,
    DOCTOR_TEMPLATE_MODE_ENTRY,
    PRE_COMMIT_CONFIG_RELPATH,
    PYTHON_PACKAGE_MARKER_RELPATH,
    PYTHON_REQUIREMENTS_RELPATH,
    TEMPLATE_PROJECT_NAME,
    TEMPLATE_SELF_TEST_RELPATH,
    clean_python_scaffolding,
    configure_doctor_precommit_hook,
    configure_language_profile,
    configure_repository_seo,
    ensure_agent_state_scratchpad,
)
from check_docs_review import check_docs
from release import apply_changelog_release

REPO_ROOT = Path(__file__).parent.parent
TODAY = datetime.today().strftime('%Y-%m-%d')

STALE_SEED_TEXT = (
    "# Active AI Agent Work State (Ephemeral Scratchpad)\n\n"
    "- **Repository**: `ai-agent-template`\n\n"
    "<!-- markdownlint-disable MD049 -->\n"
    "---\n"
    "*Last Updated: 2020-01-01* | *Last Reviewed: 2020-01-01*\n"
)

def write_stale_seed(root_dir: Path) -> Path:
    """Seed a tree with an agent-state template whose footer is long expired."""
    seed_path = root_dir / AGENT_STATE_SEED_RELPATH
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(STALE_SEED_TEXT, encoding='utf-8')
    return seed_path

# --- #80: the seeded scratchpad must not inherit the seed's frozen footer -----

def test_agent_state_scratchpad_footer_refreshed_to_bootstrap_date(tmp_path):
    write_stale_seed(tmp_path)

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project') is True

    created = (tmp_path / '.agent-state.md').read_text(encoding='utf-8')
    assert f"*Last Updated: {TODAY}* | *Last Reviewed: {TODAY}*" in created
    assert '2020-01-01' not in created

def test_seeded_scratchpad_satisfies_documentation_review_policy(tmp_path):
    seed_path = write_stale_seed(tmp_path)

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project') is True

    # Remove the seed so only the freshly created scratchpad is under review.
    seed_path.unlink()
    assert check_docs(180, 180, 180, root_dir=tmp_path) is True

def test_agent_state_scratchpad_without_footer_is_left_for_append_timestamps(tmp_path):
    seed_path = tmp_path / AGENT_STATE_SEED_RELPATH
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text("# Scratchpad\n\nNo footer at all.\n", encoding='utf-8')

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project') is True

    created = (tmp_path / '.agent-state.md').read_text(encoding='utf-8')
    assert 'Last Updated' not in created

# --- #56: a substitution that matches nothing must abort, not warn ------------

def test_configure_language_profile_aborts_when_test_command_line_missing(tmp_path):
    agents_path = tmp_path / 'AGENTS.md'
    agents_path.write_text("# Rules\n\nNothing resembling the target line.\n", encoding='utf-8')

    with pytest.raises(SystemExit) as raised:
        configure_language_profile(tmp_path, 'python')

    assert raised.value.code == 1

# --- #55: the shipped dev requirements must be language agnostic --------------

def test_requirements_dev_excludes_python_project_test_dependencies():
    agnostic = (REPO_ROOT / 'requirements-dev.txt').read_text(encoding='utf-8')
    assert 'pytest' not in agnostic
    assert 'pre-commit' in agnostic

def test_python_project_requirements_file_carries_pytest():
    python_requirements = REPO_ROOT / 'requirements-python.txt'
    assert python_requirements.exists()
    assert 'pytest' in python_requirements.read_text(encoding='utf-8')

# --- #55: --clean-template must scrub the template's Python scaffolding -------

def make_scaffolded_tree(tmp_path: Path) -> Path:
    (tmp_path / TEMPLATE_SELF_TEST_RELPATH).mkdir(parents=True)
    (tmp_path / TEMPLATE_SELF_TEST_RELPATH / 'test_template_scripts.py').write_text(
        "# template self-test\n", encoding='utf-8')
    (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).parent.mkdir(parents=True)
    (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).write_text('"""placeholder"""\n', encoding='utf-8')
    (tmp_path / PYTHON_REQUIREMENTS_RELPATH).write_text("pytest==9.1.1\n", encoding='utf-8')
    return tmp_path

@pytest.mark.parametrize('language', ['go', 'rust', 'node', 'generic'])
def test_clean_template_scrubs_python_scaffolding_for_other_languages(tmp_path, language):
    make_scaffolded_tree(tmp_path)

    removed = clean_python_scaffolding(tmp_path, language)

    assert removed == sorted([
        PYTHON_REQUIREMENTS_RELPATH.as_posix(),
        PYTHON_PACKAGE_MARKER_RELPATH.as_posix(),
        TEMPLATE_SELF_TEST_RELPATH.as_posix(),
    ])
    assert not (tmp_path / TEMPLATE_SELF_TEST_RELPATH).exists()
    assert not (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).exists()
    assert not (tmp_path / PYTHON_REQUIREMENTS_RELPATH).exists()

def test_clean_template_keeps_python_artifacts_for_python_projects(tmp_path):
    make_scaffolded_tree(tmp_path)

    removed = clean_python_scaffolding(tmp_path, 'python')

    # The self-tests test the bootstrapper that has just run, so they go regardless.
    assert removed == [TEMPLATE_SELF_TEST_RELPATH.as_posix()]
    assert (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).exists()
    assert (tmp_path / PYTHON_REQUIREMENTS_RELPATH).exists()

def test_clean_python_scaffolding_is_idempotent(tmp_path):
    make_scaffolded_tree(tmp_path)
    clean_python_scaffolding(tmp_path, 'go')

    assert clean_python_scaffolding(tmp_path, 'go') == []

# --- #56: --dry-run must preview without mutating -----------------------------

def test_dry_run_leaves_the_language_profile_untouched(tmp_path):
    agents_path = tmp_path / 'AGENTS.md'
    original = "# Rules\n\nPrimary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`\n"
    agents_path.write_text(original, encoding='utf-8')

    configure_language_profile(tmp_path, 'rust', dry_run=True)

    assert agents_path.read_text(encoding='utf-8') == original

def test_dry_run_leaves_the_scratchpad_uncreated(tmp_path):
    write_stale_seed(tmp_path)

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project', dry_run=True) is True
    assert not (tmp_path / '.agent-state.md').exists()

def test_dry_run_removes_no_scaffolding(tmp_path):
    make_scaffolded_tree(tmp_path)

    removed = clean_python_scaffolding(tmp_path, 'go', dry_run=True)

    assert removed == sorted([
        PYTHON_REQUIREMENTS_RELPATH.as_posix(),
        PYTHON_PACKAGE_MARKER_RELPATH.as_posix(),
        TEMPLATE_SELF_TEST_RELPATH.as_posix(),
    ])
    assert (tmp_path / TEMPLATE_SELF_TEST_RELPATH).exists()
    assert (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).exists()

# --- #56: the adopter's doctor hook is hardened to strict mode ----------------

def test_doctor_precommit_hook_is_switched_to_adopter_mode(tmp_path):
    config_path = tmp_path / PRE_COMMIT_CONFIG_RELPATH
    config_path.write_text(f"      entry: python3 {DOCTOR_TEMPLATE_MODE_ENTRY}\n", encoding='utf-8')

    assert configure_doctor_precommit_hook(tmp_path) is True

    rewritten = config_path.read_text(encoding='utf-8')
    assert DOCTOR_TEMPLATE_MODE_ENTRY not in rewritten
    assert DOCTOR_ADOPTER_MODE_ENTRY in rewritten

def test_doctor_precommit_hook_rewrite_is_skipped_in_dry_run(tmp_path):
    config_path = tmp_path / PRE_COMMIT_CONFIG_RELPATH
    original = f"      entry: python3 {DOCTOR_TEMPLATE_MODE_ENTRY}\n"
    config_path.write_text(original, encoding='utf-8')

    assert configure_doctor_precommit_hook(tmp_path, dry_run=True) is True
    assert config_path.read_text(encoding='utf-8') == original

def test_repository_seo_is_pinned_to_the_project_directory(tmp_path, monkeypatch):
    """`gh repo edit` resolves its target from the cwd, so it must run inside root_dir."""
    recorded = {}

    class SucceedingRun:
        returncode = 0
        stderr = ''

    def record_run(cmd, **kwargs):
        recorded['cwd'] = kwargs.get('cwd')
        return SucceedingRun()

    monkeypatch.setattr(bootstrap_template.shutil, 'which', lambda name: '/usr/bin/gh')
    monkeypatch.setattr(bootstrap_template.subprocess, 'run', record_run)

    configure_repository_seo(repo_topics=['ai-agent'], root_dir=tmp_path)

    assert recorded['cwd'] == tmp_path

def test_repository_seo_makes_no_remote_call_in_dry_run(tmp_path, monkeypatch):
    def forbidden_run(cmd, **kwargs):
        raise AssertionError(f"dry run must not invoke: {cmd}")

    monkeypatch.setattr(bootstrap_template.shutil, 'which', lambda name: '/usr/bin/gh')
    monkeypatch.setattr(bootstrap_template.subprocess, 'run', forbidden_run)

    configure_repository_seo(repo_topics=['ai-agent'], root_dir=tmp_path, dry_run=True)

# --- #56: the documented Quickstart must actually work end to end ------------
#
# The unit suite passed while the tool could not bootstrap itself: the default --name
# was 'my-ai-project', which the doctor rejects as a placeholder. These tests run the
# real script against a real copy of the tree, which is the only thing that would have
# caught it.

# Matches both fenced-block and inline-code invocations, following backslash line
# continuations and stopping at the closing backtick of an inline span.
BOOTSTRAP_INVOCATION_REGEX = re.compile(
    r'python3 scripts/bootstrap_template\.py((?:[^\n\\`]*\\\n)*[^\n`]*)')

DOCS_DOCUMENTING_BOOTSTRAP = ['README.md', 'docs/TEMPLATE_GUIDE.md']

QUICKSTART_ARGS = [
    '--name', 'my-awesome-app',
    '--lang', 'go',
    '--repo-owner', 'my-org',
    '--conduct-email', 'conduct@example.com',
]

IGNORED_COPY_PATTERNS = shutil.ignore_patterns(
    '.git', '.pytest_cache', '__pycache__', 'worktrees', '.agent-state.md')

def make_isolated_clone(tmp_path: Path):
    """Copy the working tree into tmp_path as a fresh clone would look, plus a hermetic PATH.

    The PATH carries git (check_system_dependencies requires it) but neither gh nor
    pre-commit, so the run cannot reach a remote repository or install hook environments.
    """
    project = tmp_path / 'clone'
    shutil.copytree(REPO_ROOT, project, symlinks=True, ignore=IGNORED_COPY_PATTERNS)

    isolated_bin = tmp_path / 'bin'
    isolated_bin.mkdir()
    (isolated_bin / 'git').symlink_to(shutil.which('git'))

    return project, dict(os.environ, PATH=str(isolated_bin))

def run_bootstrap(project: Path, env: dict, args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(project / 'scripts' / 'bootstrap_template.py'), *args],
        cwd=project, env=env, capture_output=True, text=True, check=False)

def fingerprint_tree(root: Path) -> dict:
    """Hash every file, symlink target and directory, ignoring Python bytecode caches."""
    entries = {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if '__pycache__' in rel or rel.endswith('.pyc'):
            continue
        if path.is_symlink():
            entries[rel] = 'symlink:' + os.readlink(path)
        elif path.is_file():
            entries[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            entries[rel] = 'dir'
    return entries

def documented_bootstrap_invocations() -> list:
    """Return (source, args) for every bootstrap command documented in the shipped docs."""
    invocations = []
    for rel_path in DOCS_DOCUMENTING_BOOTSTRAP:
        text = (REPO_ROOT / rel_path).read_text(encoding='utf-8')
        for match in BOOTSTRAP_INVOCATION_REGEX.finditer(text):
            invocations.append((rel_path, shlex.split(match.group(1).replace('\\\n', ' '))))
    return invocations

def test_the_docs_document_bootstrap_invocations_in_every_file():
    sources = {source for source, _ in documented_bootstrap_invocations()}
    assert sources == set(DOCS_DOCUMENTING_BOOTSTRAP)

def test_every_documented_invocation_satisfies_the_cli_contract():
    """A documented command that argparse rejects is a broken Quickstart."""
    for source, args in documented_bootstrap_invocations():
        parsed = bootstrap_template.build_arg_parser().parse_args(args)
        assert parsed.name and parsed.repo_owner and parsed.conduct_email, f"{source}: {args}"

def test_documented_quickstart_invocation_bootstraps_successfully(tmp_path):
    project, env = make_isolated_clone(tmp_path)

    result = run_bootstrap(project, env, QUICKSTART_ARGS)

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Bootstrap completed successfully' in result.stdout
    assert (project / '.agent-state.md').is_file()

    # The gate bootstrap just passed must still pass when run standalone.
    verification = subprocess.run(
        [sys.executable, str(project / 'scripts' / 'doctor.py'), '--dir', str(project)],
        capture_output=True, text=True, check=False)
    assert verification.returncode == 0, verification.stdout + verification.stderr

def test_documented_dry_run_leaves_the_tree_byte_identical(tmp_path):
    project, env = make_isolated_clone(tmp_path)
    before = fingerprint_tree(project)

    result = run_bootstrap(project, env, QUICKSTART_ARGS + ['--dry-run'])

    assert result.returncode == 0, result.stdout + result.stderr
    assert fingerprint_tree(project) == before

@pytest.mark.parametrize('omitted', ['--name', '--repo-owner', '--conduct-email'])
def test_omitting_a_required_flag_fails_before_any_file_is_modified(tmp_path, omitted):
    project, env = make_isolated_clone(tmp_path)
    before = fingerprint_tree(project)

    args = list(QUICKSTART_ARGS)
    del args[args.index(omitted):args.index(omitted) + 2]
    result = run_bootstrap(project, env, args)

    # argparse exits 2 on a usage error, distinct from the doctor's exit 1.
    assert result.returncode == 2
    assert 'the following arguments are required' in result.stderr
    assert omitted in result.stderr
    assert fingerprint_tree(project) == before

def test_doctor_precommit_hook_absence_is_reported_not_fatal(tmp_path):
    config_path = tmp_path / PRE_COMMIT_CONFIG_RELPATH
    config_path.write_text("repos: []\n", encoding='utf-8')

    assert configure_doctor_precommit_hook(tmp_path) is False

# --- #105: --clean-template must not hand over this template's release history ---
#
# CHANGELOG.md is an input to shipped tooling: scripts/release.py reads it to draft
# notes and --extract-notes publishes a section verbatim. An inherited version section
# therefore does not merely read wrong, it collides with the adopter's first release.

VERSION_HEADING_REGEX = re.compile(r'^## \[[^\]]+\].*$', re.MULTILINE)

CLEANED_PROJECT_NAME = 'my-awesome-app'
CLEANED_REPO_OWNER = 'my-org'
CLEANED_CONDUCT_EMAIL = 'conduct@example.com'
CLEANED_REPO_URL = f"https://github.com/{CLEANED_REPO_OWNER}/{CLEANED_PROJECT_NAME}"

@pytest.fixture(scope='module')
def cleaned_project(tmp_path_factory):
    """The project tree a real `--clean-template` bootstrap hands to an adopter.

    Module-scoped because bootstrap is a full subprocess run over a copied tree: every
    assertion about the delivered artefacts reads this single run rather than repeating it.
    """
    project, env = make_isolated_clone(tmp_path_factory.mktemp('cleaned'))

    result = run_bootstrap(project, env, QUICKSTART_ARGS + ['--clean-template'])

    assert result.returncode == 0, result.stdout + result.stderr
    return project

@pytest.fixture(scope='module')
def cleaned_changelog(cleaned_project):
    """The CHANGELOG.md a real `--clean-template` bootstrap hands to an adopter."""
    return (cleaned_project / 'CHANGELOG.md').read_text(encoding='utf-8')

def test_clean_template_leaves_no_inherited_version_section(cleaned_changelog):
    headings = VERSION_HEADING_REGEX.findall(cleaned_changelog)

    assert headings == ['## [Unreleased]'], headings

def test_clean_template_leaves_no_reference_to_this_templates_pull_requests(cleaned_changelog):
    assert re.findall(r'#\d+', cleaned_changelog) == []
    assert TEMPLATE_PROJECT_NAME not in cleaned_changelog

def test_clean_template_changelog_points_its_links_at_the_adopters_repository(cleaned_changelog):
    assert f"[Unreleased]: {CLEANED_REPO_URL}/compare/main...HEAD" in cleaned_changelog

def test_release_cuts_a_clean_first_release_from_the_cleaned_changelog(cleaned_changelog):
    """The point of the reset: release.py must still be usable in the adopter's repo."""
    # release.py bumps into the repository's tag format, so the version carries its `v`.
    released = apply_changelog_release(cleaned_changelog, 'v1.0.0', '2026-01-31', [])

    assert VERSION_HEADING_REGEX.findall(released) == [
        '## [Unreleased]', '## [1.0.0] - 2026-01-31']
    assert released.count(f"[1.0.0]: {CLEANED_REPO_URL}/releases/tag/v1.0.0") == 1
    assert f"[Unreleased]: {CLEANED_REPO_URL}/compare/v1.0.0...HEAD" in released

# --- #107: the delivered security policy must be the adopter's, and must be actionable ---
#
# SECURITY.md is a GitHub community health file, surfaced in the repository sidebar and the
# "Report a vulnerability" flow. Two failure modes matter, in increasing order of severity:
# naming the template tells a reporter they are reading someone else's policy, and naming
# no destination at all fails the one job the document exists to do.

@pytest.fixture(scope='module')
def bootstrapped_security_policy(cleaned_project):
    """The SECURITY.md a real `--clean-template` bootstrap hands to an adopter."""
    return (cleaned_project / 'SECURITY.md').read_text(encoding='utf-8')

def test_bootstrap_security_policy_names_the_adopters_project(bootstrapped_security_policy):
    assert TEMPLATE_PROJECT_NAME not in bootstrapped_security_policy
    assert CLEANED_PROJECT_NAME in bootstrapped_security_policy

def test_bootstrap_security_policy_names_a_contactable_reporting_destination(bootstrapped_security_policy):
    """Disclosure instructions naming no address are worse than naming the wrong project."""
    assert CONDUCT_EMAIL_PLACEHOLDER not in bootstrapped_security_policy
    assert CLEANED_CONDUCT_EMAIL in bootstrapped_security_policy

# --- #109: no delivered document may cite a path the same bootstrap removed ---
#
# SECURITY.md linked tests/test_workflow_pinning.py to make a real point -- that the
# SHA-pinning rule is enforced from the inside by a test and not merely flagged by a
# scanner -- and --clean-template deletes tests/, so the delivered policy argued from a
# file the same run had removed. Three defects of this shape shipped in sequence (#105,
# #107, #109), each found by auditing the one file just fixed, so the invariant is
# asserted here in general rather than against that one sentence: whatever the cleanup
# deletes, no surviving document may still point at it.
#
# The removed set is diffed out of a real run rather than restated as a list, so a path
# added to the cleanup later is covered without anyone remembering to extend this test.

@pytest.fixture(scope='module')
def clean_template_removals(tmp_path_factory, cleaned_project):
    """Relative POSIX paths --clean-template removed from the tree handed to an adopter.

    The opt-in documentation site is excluded: it is absent by choice rather than by
    cleanup, and docs/how-to/publish-the-documentation-site.md exists to explain how to
    restore it, so naming those files is the doc doing its job.
    """
    pristine, _ = make_isolated_clone(tmp_path_factory.mktemp('pristine'))
    opt_in = {rel_path.as_posix() for rel_path in DOCS_SITE_SCAFFOLD_RELPATHS}

    removed = set(fingerprint_tree(pristine)) - set(fingerprint_tree(cleaned_project))
    return removed - opt_in

def test_no_delivered_document_cites_a_path_clean_template_removed(
        cleaned_project, clean_template_removals):
    # Only paths carrying a separator are matched: a bare `tests` or `src` is an ordinary
    # English word ("unit tests pass") long before it is a citation of a directory.
    citable = sorted(rel for rel in clean_template_removals if '/' in rel)
    assert citable, "diff produced no citable removals; the fixture is not exercising cleanup"

    citations = []
    for markdown_path in sorted(cleaned_project.rglob('*.md')):
        rel_path = markdown_path.relative_to(cleaned_project).as_posix()
        # .claude/skills is a symlink onto .agents/skills; scanning both double-reports.
        if rel_path.startswith('.claude/skills/'):
            continue
        text = markdown_path.read_text(encoding='utf-8')
        citations.extend(f"{rel_path} cites {cited}" for cited in citable if cited in text)

    assert citations == [], citations
