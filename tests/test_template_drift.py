"""
test_template_drift.py - Unit Test Suite for the Upstream Template Drift Checker

Covers scripts/check_template_drift.py and the .agents/templates/template-ref.md seed
that scripts/bootstrap_template.py materialises into an adopter's .agents/TEMPLATE_REF.md.

Deliberately a separate module from test_template_scripts.py: that file is the historic
source of merge conflicts in this repository and is already large.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Add scripts directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from check_template_drift import (
    DEFAULT_UPSTREAM_REMOTE_REF,
    GOVERNED_PATHS,
    NEVER_CHECKED_VALUE,
    TEMPLATE_REFERENCE_RELPATH,
    TEMPLATE_REFERENCE_SEED_RELPATH,
    TEMPLATE_REPO_URL,
    UNKNOWN_STAMP_VALUE,
    TemplateReferenceError,
    apply_reference_stamp,
    compare_paths,
    fetch_upstream_snapshot,
    main,
    normalise_for_comparison,
    parse_template_reference,
    resolve_local_template_stamp,
    summarise_upstream_changes,
)
from bootstrap_template import ensure_template_reference

REPO_ROOT = Path(__file__).parent.parent

# The exact stanza hand-maintained today in lfr-tunnel/.agents/TEMPLATE_REF.md and
# liferay-ai-commerce-accelerator/.agents/TEMPLATE_REF.md. The parser must read the
# wording those repositories already use, so the checker works on them unmodified.
DOWNSTREAM_REFERENCE_STANZA = """# Template Reference

Some prose about why this file exists.

**Reference repo**: <https://github.com/peterrichards-lr/ai-agent-template>
**Reference version at last check**: `v1.2.0` (origin/main @ `83b1cf2`, 2026-08-01)
**Last checked**: 2026-08-05

## Known drift as of this check

- [#931](https://github.com/peterrichards-lr/lfr-tunnel/issues/931) - a real downstream issue.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-08-05* | *Last Reviewed: 2026-08-05*
"""


def run_git(args, cwd):
    """Run git non-interactively in a temporary fixture repository."""
    return subprocess.run(
        ['git', '-c', 'user.email=test@example.com', '-c', 'user.name=Test'] + args,
        cwd=str(cwd), capture_output=True, text=True, check=True,
    )


@pytest.fixture
def upstream_repo(tmp_path):
    """A real local git repository standing in for the upstream template.

    Uses a file:// URL so the whole fetch/diff path is exercised for real without
    touching the network.
    """
    origin = tmp_path / 'upstream'
    (origin / '.agents' / 'skills' / 'unit-testing').mkdir(parents=True)
    (origin / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').write_text(
        "# Skill\n\nOriginal rule.\n\n---\n*Last Updated: 2026-01-01* | *Last Reviewed: 2026-01-01*\n",
        encoding='utf-8')
    (origin / 'AGENTS.md').write_text("# Agents\n\nbaseline\n", encoding='utf-8')

    run_git(['init', '--quiet', '--initial-branch=main', '.'], origin)
    run_git(['add', '.agents', 'AGENTS.md'], origin)
    run_git(['commit', '--quiet', '-m', 'baseline'], origin)
    baseline_commit = run_git(['rev-parse', 'HEAD'], origin).stdout.strip()
    run_git(['tag', 'v1.0.0'], origin)

    # A second upstream commit: exactly the "changed upstream since your last check"
    # situation this script exists to surface.
    (origin / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').write_text(
        "# Skill\n\nHardened rule.\n\n---\n*Last Updated: 2026-02-02* | *Last Reviewed: 2026-02-02*\n",
        encoding='utf-8')
    run_git(['add', '.agents'], origin)
    run_git(['commit', '--quiet', '-m', 'harden the unit-testing rule'], origin)
    head_commit = run_git(['rev-parse', 'HEAD'], origin).stdout.strip()

    return {
        'path': origin,
        'url': origin.as_uri(),
        'baseline_commit': baseline_commit,
        'head_commit': head_commit,
    }


def write_reference_file(root: Path, repo_url: str, commit: str, version: str = 'v1.0.0') -> Path:
    """Write a minimal but valid .agents/TEMPLATE_REF.md into a fixture repository."""
    reference_path = root / TEMPLATE_REFERENCE_RELPATH
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_text(
        "# Template Reference\n\n"
        f"**Reference repo**: <{repo_url}>\n"
        f"**Reference version at last check**: `{version}` (origin/main @ `{commit}`, 2026-01-01)\n"
        "**Last checked**: 2026-01-01\n\n"
        "## Known drift as of this check\n\n- None recorded.\n\n"
        "---\n*Last Updated: 2026-01-01* | *Last Reviewed: 2026-01-01*\n",
        encoding='utf-8')
    return reference_path


# --------------------------------------------------------------------------------------
# Parsing the reference stanza the downstream repositories already hand-maintain
# --------------------------------------------------------------------------------------

def test_parses_the_wording_downstream_repos_already_use():
    reference = parse_template_reference(DOWNSTREAM_REFERENCE_STANZA)

    assert reference.repo_url == 'https://github.com/peterrichards-lr/ai-agent-template'
    assert reference.version == 'v1.2.0'
    assert reference.upstream_ref == 'origin/main'
    assert reference.commit == '83b1cf2'
    assert reference.commit_date == '2026-08-01'
    assert reference.last_checked == '2026-08-05'


def test_parse_rejects_a_file_without_a_reference_stanza():
    with pytest.raises(TemplateReferenceError):
        parse_template_reference("# Template Reference\n\nNothing machine readable here.\n")


def test_parse_reports_an_unstamped_baseline_rather_than_failing():
    """A freshly bootstrapped file records `unknown`/`never`; that is a state, not an error."""
    content = (
        "# Template Reference\n\n"
        f"**Reference repo**: <{TEMPLATE_REPO_URL}>\n"
        f"**Reference version at last check**: `{UNKNOWN_STAMP_VALUE}` "
        f"({DEFAULT_UPSTREAM_REMOTE_REF} @ `{UNKNOWN_STAMP_VALUE}`, {UNKNOWN_STAMP_VALUE})\n"
        f"**Last checked**: {NEVER_CHECKED_VALUE}\n"
    )
    reference = parse_template_reference(content)

    assert reference.commit == UNKNOWN_STAMP_VALUE
    assert reference.is_stamped is False


def test_apply_reference_stamp_rewrites_both_lines_and_refreshes_the_footer():
    updated = apply_reference_stamp(
        DOWNSTREAM_REFERENCE_STANZA,
        version='v1.4.0',
        upstream_ref='origin/main',
        commit='deadbee',
        commit_date='2026-09-01',
        checked_on='2026-09-05',
    )
    reference = parse_template_reference(updated)

    assert reference.version == 'v1.4.0'
    assert reference.commit == 'deadbee'
    assert reference.commit_date == '2026-09-01'
    assert reference.last_checked == '2026-09-05'
    assert reference.is_stamped is True
    # The drift list and prose must survive a stamp update untouched.
    assert 'lfr-tunnel/issues/931' in updated
    # The document footer is refreshed so the stamped file does not immediately
    # violate the documentation review policy.
    assert '*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*' in updated


# --------------------------------------------------------------------------------------
# Comparing local governance files against the upstream snapshot
# --------------------------------------------------------------------------------------

def test_apply_reference_stamp_preserves_the_blank_line_before_the_next_heading():
    """A greedy `\\s*$` in the stamp regexes swallows the newline separating the stanza
    from the '## Known drift' heading, producing Markdown that violates MD022."""
    updated = apply_reference_stamp(
        DOWNSTREAM_REFERENCE_STANZA,
        version='v1.4.0', upstream_ref='origin/main', commit='deadbee',
        commit_date='2026-09-01', checked_on='2026-09-05',
    )

    assert '**Last checked**: 2026-09-05\n\n## Known drift' in updated


def test_timestamp_footer_only_edits_are_not_reported_as_drift():
    """Every adopter's footers differ by construction; only real content is drift."""
    upstream = "# Skill\n\nRule.\n\n---\n*Last Updated: 2026-01-01* | *Last Reviewed: 2026-01-01*\n"
    local_footer_only = "# Skill\n\nRule.\n\n---\n*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*\n"
    local_real_change = "# Skill\n\nDifferent rule.\n\n---\n*Last Updated: 2026-01-01* | *Last Reviewed: 2026-01-01*\n"

    assert normalise_for_comparison(upstream, Path('SKILL.md')) == \
        normalise_for_comparison(local_footer_only, Path('SKILL.md'))
    assert normalise_for_comparison(upstream, Path('SKILL.md')) != \
        normalise_for_comparison(local_real_change, Path('SKILL.md'))


def test_compare_paths_classifies_missing_added_and_modified_files(tmp_path):
    upstream_root = tmp_path / 'upstream'
    local_root = tmp_path / 'local'
    for root in (upstream_root, local_root):
        (root / '.agents' / 'skills' / 'documentation').mkdir(parents=True)

    (upstream_root / '.agents' / 'skills' / 'documentation' / 'SKILL.md').write_text('same\n', encoding='utf-8')
    (local_root / '.agents' / 'skills' / 'documentation' / 'SKILL.md').write_text('same\n', encoding='utf-8')

    (upstream_root / '.agents' / 'skills' / 'brand-new').mkdir(parents=True)
    (upstream_root / '.agents' / 'skills' / 'brand-new' / 'SKILL.md').write_text('new upstream\n', encoding='utf-8')

    (local_root / '.agents' / 'skills' / 'local-only').mkdir(parents=True)
    (local_root / '.agents' / 'skills' / 'local-only' / 'SKILL.md').write_text('local\n', encoding='utf-8')

    (upstream_root / 'AGENTS.md').write_text('upstream rules\n', encoding='utf-8')
    (local_root / 'AGENTS.md').write_text('diverged rules\n', encoding='utf-8')

    comparison = compare_paths(upstream_root, local_root, ['.agents/skills', 'AGENTS.md'])

    assert '.agents/skills/brand-new/SKILL.md' in comparison.only_upstream
    assert '.agents/skills/local-only/SKILL.md' in comparison.only_local
    assert 'AGENTS.md' in comparison.modified
    assert '.agents/skills/documentation/SKILL.md' not in comparison.modified
    assert comparison.has_drift is True


def test_compare_paths_reports_no_drift_for_an_identical_checkout(tmp_path):
    upstream_root = tmp_path / 'upstream'
    local_root = tmp_path / 'local'
    for root in (upstream_root, local_root):
        root.mkdir()
        (root / 'AGENTS.md').write_text('identical\n', encoding='utf-8')

    comparison = compare_paths(upstream_root, local_root, ['AGENTS.md'])

    assert comparison.has_drift is False


def test_a_path_absent_from_both_sides_is_not_drift(tmp_path):
    """Adopters legitimately delete template-only paths; absence on both sides is silence."""
    upstream_root = tmp_path / 'upstream'
    local_root = tmp_path / 'local'
    upstream_root.mkdir()
    local_root.mkdir()

    comparison = compare_paths(upstream_root, local_root, ['docs/TEMPLATE_GUIDE.md'])

    assert comparison.has_drift is False


# --------------------------------------------------------------------------------------
# Fetching the upstream snapshot (real git, file:// URL, no network)
# --------------------------------------------------------------------------------------

def test_fetch_upstream_snapshot_reads_head_version_and_commit(tmp_path, upstream_repo):
    snapshot = fetch_upstream_snapshot(upstream_repo['url'], tmp_path / 'clone')

    assert snapshot.ok is True
    assert snapshot.head_commit.startswith(upstream_repo['head_commit'][:7])
    assert snapshot.head_version == 'v1.0.0'
    assert (snapshot.worktree / 'AGENTS.md').exists()


def test_fetch_upstream_snapshot_degrades_gracefully_when_the_remote_is_unreachable(tmp_path):
    snapshot = fetch_upstream_snapshot(
        'https://invalid.invalid/does-not-exist.git', tmp_path / 'clone')

    assert snapshot.ok is False
    assert snapshot.reason


def test_summarise_upstream_changes_lists_commits_and_paths_since_the_recorded_ref(tmp_path, upstream_repo):
    snapshot = fetch_upstream_snapshot(upstream_repo['url'], tmp_path / 'clone')
    changes = summarise_upstream_changes(
        snapshot.worktree, upstream_repo['baseline_commit'], GOVERNED_PATHS)

    assert changes.recorded_commit_found is True
    assert any('harden the unit-testing rule' in line for line in changes.commits)
    assert '.agents/skills/unit-testing/SKILL.md' in changes.changed_paths


def test_resolve_local_template_stamp_reads_a_real_checkout(upstream_repo):
    version, commit, commit_date = resolve_local_template_stamp(upstream_repo['path'])

    assert version == 'v1.0.0'
    assert upstream_repo['head_commit'].startswith(commit)
    assert commit_date.count('-') == 2


def test_resolve_local_template_stamp_falls_back_to_unknown_outside_git(tmp_path):
    """A 'Use this template' repository has no upstream history; say so rather than lie."""
    plain_directory = tmp_path / 'not-a-repo'
    plain_directory.mkdir()

    assert resolve_local_template_stamp(plain_directory) == (
        UNKNOWN_STAMP_VALUE, UNKNOWN_STAMP_VALUE, UNKNOWN_STAMP_VALUE)


def test_summarise_upstream_changes_survives_an_unknown_recorded_commit(tmp_path, upstream_repo):
    snapshot = fetch_upstream_snapshot(upstream_repo['url'], tmp_path / 'clone')
    changes = summarise_upstream_changes(snapshot.worktree, UNKNOWN_STAMP_VALUE, GOVERNED_PATHS)

    assert changes.recorded_commit_found is False
    assert changes.commits == []


# --------------------------------------------------------------------------------------
# End-to-end CLI behaviour and exit codes
# --------------------------------------------------------------------------------------

def test_cli_reports_drift_and_exits_zero_by_default(tmp_path, upstream_repo, capsys):
    local_root = tmp_path / 'local'
    (local_root / '.agents' / 'skills' / 'unit-testing').mkdir(parents=True)
    (local_root / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').write_text(
        "# Skill\n\nLocally diverged rule.\n", encoding='utf-8')
    write_reference_file(local_root, upstream_repo['url'], upstream_repo['baseline_commit'])

    exit_code = main(['--root', str(local_root)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert 'harden the unit-testing rule' in output
    assert '.agents/skills/unit-testing/SKILL.md' in output


def test_cli_fail_on_drift_turns_a_report_into_a_gate(tmp_path, upstream_repo):
    local_root = tmp_path / 'local'
    (local_root / '.agents' / 'skills' / 'unit-testing').mkdir(parents=True)
    (local_root / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').write_text(
        "# Skill\n\nLocally diverged rule.\n", encoding='utf-8')
    write_reference_file(local_root, upstream_repo['url'], upstream_repo['baseline_commit'])

    assert main(['--root', str(local_root), '--fail-on-drift']) == 2


def test_cli_exits_zero_and_warns_when_the_upstream_is_unreachable(tmp_path, capsys):
    """An offline checkout must never be a hard failure -- issue #48's explicit requirement."""
    local_root = tmp_path / 'local'
    write_reference_file(local_root, 'https://invalid.invalid/nope.git', 'abc1234')

    exit_code = main(['--root', str(local_root), '--fail-on-drift'])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert 'offline' in output.lower() or 'could not reach' in output.lower()


def test_cli_exits_nonzero_when_the_reference_file_is_missing(tmp_path, capsys):
    exit_code = main(['--root', str(tmp_path)])
    error_output = capsys.readouterr().err

    assert exit_code == 1
    assert TEMPLATE_REFERENCE_RELPATH.as_posix() in error_output


def test_cli_update_stamp_rewrites_the_recorded_ref_in_place(tmp_path, upstream_repo):
    local_root = tmp_path / 'local'
    reference_path = write_reference_file(
        local_root, upstream_repo['url'], upstream_repo['baseline_commit'])

    assert main(['--root', str(local_root), '--update-stamp']) == 0

    reference = parse_template_reference(reference_path.read_text(encoding='utf-8'))
    assert reference.commit.startswith(upstream_repo['head_commit'][:7])
    assert reference.last_checked != '2026-01-01'


def test_cli_leaves_the_stamp_alone_without_update_stamp(tmp_path, upstream_repo):
    local_root = tmp_path / 'local'
    reference_path = write_reference_file(
        local_root, upstream_repo['url'], upstream_repo['baseline_commit'])
    before = reference_path.read_text(encoding='utf-8')

    assert main(['--root', str(local_root)]) == 0
    assert reference_path.read_text(encoding='utf-8') == before


# --------------------------------------------------------------------------------------
# The shipped seed, and bootstrap materialising it
# --------------------------------------------------------------------------------------

def test_template_ships_the_seed_and_not_a_live_self_referential_reference_file():
    """Design decision for #48: the template is the upstream, so it seeds rather than carries."""
    assert (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).exists()
    assert not (REPO_ROOT / TEMPLATE_REFERENCE_RELPATH).exists(), (
        "The template repository is the upstream; a live .agents/TEMPLATE_REF.md here "
        "would point at itself."
    )


def test_shipped_seed_parses_and_starts_unstamped():
    seed = (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).read_text(encoding='utf-8')
    reference = parse_template_reference(seed)

    assert reference.repo_url == TEMPLATE_REPO_URL
    assert reference.is_stamped is False
    assert reference.last_checked == NEVER_CHECKED_VALUE


def test_shipped_seed_states_the_bidirectional_contract():
    seed = (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).read_text(encoding='utf-8')

    assert 'Known drift' in seed
    assert 'check_template_drift.py' in seed
    # Both directions of the contract the downstream files already state.
    assert 'before writing a new' in seed.lower()
    assert 'upstream' in seed.lower()


def test_bootstrap_materialises_the_reference_file_from_the_seed(tmp_path):
    project_root = tmp_path / 'project'
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH.parent).mkdir(parents=True)
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH).write_text(
        (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).read_text(encoding='utf-8'),
        encoding='utf-8')

    assert ensure_template_reference(project_root, 'my-downstream-app') is True

    reference_path = project_root / TEMPLATE_REFERENCE_RELPATH
    assert reference_path.exists()
    content = reference_path.read_text(encoding='utf-8')
    reference = parse_template_reference(content)
    assert reference.repo_url == TEMPLATE_REPO_URL
    assert 'my-downstream-app' in content
    assert 'PLACEHOLDER' not in content, "doctor.py fails an adopter repo on a surviving placeholder"


def test_bootstrap_does_not_rewrite_the_upstream_url_with_the_project_name(tmp_path):
    """`ai-agent-template` appears inside the upstream URL; a blanket rename would corrupt it."""
    project_root = tmp_path / 'project'
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH.parent).mkdir(parents=True)
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH).write_text(
        (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).read_text(encoding='utf-8'),
        encoding='utf-8')

    ensure_template_reference(project_root, 'my-downstream-app')

    content = (project_root / TEMPLATE_REFERENCE_RELPATH).read_text(encoding='utf-8')
    assert TEMPLATE_REPO_URL in content
    assert 'my-downstream-app' not in TEMPLATE_REPO_URL


def test_bootstrap_dry_run_writes_nothing(tmp_path):
    project_root = tmp_path / 'project'
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH.parent).mkdir(parents=True)
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH).write_text(
        (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).read_text(encoding='utf-8'),
        encoding='utf-8')

    assert ensure_template_reference(project_root, 'my-downstream-app', dry_run=True) is True
    assert not (project_root / TEMPLATE_REFERENCE_RELPATH).exists()


def test_bootstrap_warns_rather_than_crashing_when_the_seed_is_absent(tmp_path, capsys):
    project_root = tmp_path / 'project'
    project_root.mkdir()

    assert ensure_template_reference(project_root, 'my-downstream-app') is False
    assert TEMPLATE_REFERENCE_SEED_RELPATH.as_posix() in capsys.readouterr().err


def test_bootstrap_never_overwrites_an_existing_reference_file(tmp_path):
    """The drift log is hand-maintained content; re-running bootstrap must not erase it."""
    project_root = tmp_path / 'project'
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH.parent).mkdir(parents=True)
    (project_root / TEMPLATE_REFERENCE_SEED_RELPATH).write_text(
        (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).read_text(encoding='utf-8'),
        encoding='utf-8')
    reference_path = project_root / TEMPLATE_REFERENCE_RELPATH
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_text(DOWNSTREAM_REFERENCE_STANZA, encoding='utf-8')

    ensure_template_reference(project_root, 'my-downstream-app')

    assert 'lfr-tunnel/issues/931' in reference_path.read_text(encoding='utf-8')


# --------------------------------------------------------------------------------------
# The template-sync skill documenting the contract
# --------------------------------------------------------------------------------------

def test_template_sync_skill_documents_both_directions_and_the_tooling():
    skill = REPO_ROOT / '.agents' / 'skills' / 'template-sync' / 'SKILL.md'
    assert skill.exists()

    content = skill.read_text(encoding='utf-8')
    assert 'scripts/check_template_drift.py' in content
    assert TEMPLATE_REFERENCE_RELPATH.as_posix() in content
    assert 'Downstream' in content or 'downstream' in content
    assert 'Upstream' in content or 'upstream' in content
