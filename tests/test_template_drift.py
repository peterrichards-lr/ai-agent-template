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


def test_compiled_artefacts_are_never_reported_as_drift(tmp_path):
    """`scripts/__pycache__/*.pyc` exists in any working checkout and in no git tree;
    reporting it would put build noise at the top of every Python adopter's report."""
    upstream_root = tmp_path / 'upstream'
    local_root = tmp_path / 'local'
    (upstream_root / 'scripts').mkdir(parents=True)
    (local_root / 'scripts' / '__pycache__').mkdir(parents=True)

    (upstream_root / 'scripts' / 'doctor.py').write_text('same\n', encoding='utf-8')
    (local_root / 'scripts' / 'doctor.py').write_text('same\n', encoding='utf-8')
    (local_root / 'scripts' / '__pycache__' / 'doctor.cpython-314.pyc').write_bytes(b'\x00compiled')

    comparison = compare_paths(upstream_root, local_root, ['scripts'])

    assert comparison.only_local == []
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


# --------------------------------------------------------------------------------------
# #135: path mapping, mismatch evidence, direction, and failing when nothing was compared
# --------------------------------------------------------------------------------------

from check_template_drift import (  # noqa: E402
    DIRECTION_MESSAGE,
    DOCS_SITE_SHARED_PATHS,
    PATH_MAPPING_NONE_LINE,
    classify_clone_failure,
    describe_bytes,
    parse_path_mappings,
)

HOOK_UPSTREAM = 'scripts/mkdocs_github_alerts.py'
HOOK_LOCAL = 'mkdocs_hooks/github_alerts.py'
HOOK_BODY = '"""SHARED FILE."""\n_TYPES = {"NOTE": "note"}\n'


def write_mapping(reference_path: Path, *pairs):
    """Append a Path mapping section to a fixture reference file."""
    lines = '\n'.join(f'- `{local}` ← `{upstream}`' for local, upstream in pairs)
    content = reference_path.read_text(encoding='utf-8').replace(
        '## Known drift as of this check',
        f'## Path mapping\n\nProse.\n\n{lines}\n\n## Known drift as of this check')
    reference_path.write_text(content, encoding='utf-8')


@pytest.fixture
def docs_upstream(tmp_path):
    """An upstream carrying the shared docs files, at the template's paths."""
    origin = tmp_path / 'docs-upstream'
    for rel, body in ((HOOK_UPSTREAM, HOOK_BODY),
                      ('scripts/check_docs_rendered.py', '# check\n'),
                      ('scripts/check_template_drift.py', '# drift\n'),
                      ('overrides/main.html', '{% extends "base.html" %}\n'),
                      ('overrides/partials/copyright.html', '<div></div>\n'),
                      ('.agents/templates/docs-profiles/liferay/liferay-blue.css', ':root {}\n')):
        (origin / rel).parent.mkdir(parents=True, exist_ok=True)
        (origin / rel).write_text(body, encoding='utf-8')
    run_git(['init', '--quiet', '--initial-branch=main', '.'], origin)
    run_git(['add', '.'], origin)
    run_git(['commit', '--quiet', '-m', 'shared docs files'], origin)
    return {'path': origin, 'url': origin.as_uri(),
            'commit': run_git(['rev-parse', 'HEAD'], origin).stdout.strip()}


def adopter_with_docs_files(root: Path, upstream: Path, skip=(), at=None):
    """Copy the upstream's files into an adopter, optionally moving some (`at`: {up: local})."""
    at = at or {}
    for source in upstream.rglob('*'):
        rel = source.relative_to(upstream).as_posix()
        if not source.is_file() or rel.startswith('.git/') or rel in skip:
            continue
        target = root / at.get(rel, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return root


def test_parse_path_mappings_reads_only_its_own_section():
    content = (
        "# Ref\n\n- `elsewhere` ← `not-a-mapping`\n\n"
        "## Path mapping\n\nA line in prose: `a` ← `b` is not a list item.\n\n"
        f"- `{HOOK_LOCAL}` ← `{HOOK_UPSTREAM}`\n"
        "- `docs/x.css` <- `.agents/templates/x.css`\n\n"
        "---\n\n## Known drift\n\n- `after` ← `the-section`\n")
    assert parse_path_mappings(content) == {
        HOOK_UPSTREAM: HOOK_LOCAL, '.agents/templates/x.css': 'docs/x.css'}


def test_a_reference_file_without_a_mapping_section_maps_nothing():
    assert parse_path_mappings(DOWNSTREAM_REFERENCE_STANZA) == {}


def test_the_seed_ships_an_empty_path_mapping_section():
    seed = (REPO_ROOT / TEMPLATE_REFERENCE_SEED_RELPATH).read_text(encoding='utf-8')
    assert '## Path mapping' in seed and PATH_MAPPING_NONE_LINE in seed
    assert parse_path_mappings(seed) == {}


def test_a_moved_identical_file_is_compared_not_reported_twice(tmp_path, docs_upstream):
    local = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'],
                                    at={HOOK_UPSTREAM: HOOK_LOCAL})
    comparison = compare_paths(docs_upstream['path'], local, ['scripts'],
                               mappings={HOOK_UPSTREAM: HOOK_LOCAL})
    assert not comparison.has_drift, comparison
    assert comparison.missing_upstream == ()


def test_without_the_mapping_a_moved_file_reads_as_missing(tmp_path, docs_upstream):
    """The control: the same tree, no mapping, reports the hook as absent locally."""
    local = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'],
                                    at={HOOK_UPSTREAM: HOOK_LOCAL})
    comparison = compare_paths(docs_upstream['path'], local, ['scripts'])
    assert comparison.only_upstream == [HOOK_UPSTREAM]


def test_a_moved_edited_file_reports_both_hashes_and_sizes(tmp_path, docs_upstream):
    local = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'],
                                    at={HOOK_UPSTREAM: HOOK_LOCAL})
    edited = HOOK_BODY + '# a local edit\n'
    (local / HOOK_LOCAL).write_text(edited, encoding='utf-8')

    comparison = compare_paths(docs_upstream['path'], local, [HOOK_LOCAL],
                               mappings={HOOK_UPSTREAM: HOOK_LOCAL})
    assert comparison.modified == [HOOK_UPSTREAM]
    evidence = comparison.evidence[HOOK_UPSTREAM]
    assert f'local at {HOOK_LOCAL}: {describe_bytes(edited.encode())}' in evidence
    assert f'upstream: {describe_bytes(HOOK_BODY.encode())}' in evidence


def test_describe_bytes_is_a_short_sha256_and_a_size():
    import hashlib
    assert describe_bytes(b'abc') == f"sha256 {hashlib.sha256(b'abc').hexdigest()[:16]}, 3 bytes"


@pytest.mark.parametrize('stderr, not_found', [
    ("remote: Repository not found.\nfatal: repository 'https://github.com/x/y/' not found", True),
    ("fatal: could not read Username for 'https://github.com': terminal prompts disabled", True),
    ("fatal: unable to access 'https://x/': The requested URL returned error: 403", True),
    ("fatal: '/nope' does not appear to be a git repository", True),
    ("fatal: unable to access 'https://x/': Could not resolve host: x", False),
    ("fatal: unable to access 'https://x/': Failed to connect to x port 443: Operation timed out",
     False),
    ("fatal: unable to access 'https://x/': The requested URL returned error: 502", False),
    ("git clone timed out after 120s", False),
    # init.templateDir pointing nowhere adds a harmless warning containing "not found".
    ("warning: templates not found in /nonexistent/tpl\n"
     "fatal: unable to access 'https://x.invalid/a/b/': Could not resolve host: x.invalid", False),
])
def test_clone_failures_split_into_not_found_and_transport(stderr, not_found):
    assert classify_clone_failure(stderr) is not_found


def test_cli_fails_when_the_upstream_repository_does_not_exist(tmp_path, capsys):
    """A 404 will not fix itself: exit 3, never a green run that compared nothing."""
    local_root = tmp_path / 'local'
    write_reference_file(local_root, (tmp_path / 'no-such-repo').as_uri(), 'abc1234')

    assert main(['--root', str(local_root)]) == 3
    assert 'not found' in capsys.readouterr().err


def test_cli_fails_when_a_requested_path_is_missing_upstream(tmp_path, docs_upstream, capsys):
    local_root = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'])
    write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])

    assert main(['--root', str(local_root), '--path', 'overrides/renamed.html']) == 3
    captured = capsys.readouterr()
    assert 'overrides/renamed.html' in captured.out
    assert 'nothing was compared' in captured.err


def test_cli_fails_when_a_local_governed_path_has_no_upstream_counterpart(
        tmp_path, upstream_repo, capsys):
    """`overrides` exists here and not in this upstream: comparing it against nothing fails."""
    local_root = tmp_path / 'local'
    (local_root / 'overrides').mkdir(parents=True)
    (local_root / 'overrides' / 'main.html').write_text('x\n', encoding='utf-8')
    write_reference_file(local_root, upstream_repo['url'], upstream_repo['head_commit'])

    assert main(['--root', str(local_root)]) == 3


def test_cli_docs_site_mode_passes_on_byte_identical_copies(tmp_path, docs_upstream, capsys):
    local_root = adopter_with_docs_files(
        tmp_path / 'local', docs_upstream['path'],
        at={'.agents/templates/docs-profiles/liferay/liferay-blue.css':
            'docs/assets/stylesheets/liferay-blue.css'})
    reference = write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])
    write_mapping(reference, ('docs/assets/stylesheets/liferay-blue.css',
                              '.agents/templates/docs-profiles/liferay/liferay-blue.css'))

    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 0
    assert 'No drift' in capsys.readouterr().out


def test_cli_docs_site_mode_fails_a_local_edit_with_evidence_and_direction(
        tmp_path, docs_upstream, capsys):
    css_up = '.agents/templates/docs-profiles/liferay/liferay-blue.css'
    css_local = 'docs/assets/stylesheets/liferay-blue.css'
    local_root = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'],
                                         at={css_up: css_local})
    reference = write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])
    write_mapping(reference, (css_local, css_up))
    (local_root / css_local).write_text(':root { --edited: 1; }\n', encoding='utf-8')

    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 2
    out = capsys.readouterr().out
    assert f'{css_up}\n      local at {css_local}: sha256 ' in out
    assert 'upstream: sha256 ' in out
    assert DIRECTION_MESSAGE.format(repo_url=docs_upstream['url']) in out


def test_cli_accepts_a_local_path_through_its_mapping(tmp_path, docs_upstream):
    local_root = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'],
                                         at={HOOK_UPSTREAM: HOOK_LOCAL})
    reference = write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])
    write_mapping(reference, (HOOK_LOCAL, HOOK_UPSTREAM))

    assert main(['--root', str(local_root), '--path', HOOK_LOCAL, '--fail-on-drift']) == 0


def test_fail_on_drift_ignores_upstream_commits_when_content_matches(tmp_path, upstream_repo, capsys):
    """Content, not history: matching HEAD exactly passes even with commits since the stamp."""
    local_root = tmp_path / 'local'
    for rel in ('.agents/skills/unit-testing/SKILL.md', 'AGENTS.md'):
        (local_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (local_root / rel).write_bytes((upstream_repo['path'] / rel).read_bytes())
    write_reference_file(local_root, upstream_repo['url'], upstream_repo['baseline_commit'])

    assert main(['--root', str(local_root), '--fail-on-drift']) == 0
    assert 'harden the unit-testing rule' in capsys.readouterr().out, (
        "the upstream commits are still reported")


def test_docs_site_paths_are_all_shipped_by_the_template():
    for rel in DOCS_SITE_SHARED_PATHS:
        assert (REPO_ROOT / rel).exists(), f"{rel} is a docs-site shared path but not shipped"
    assert 'overrides/main.html' in GOVERNED_PATHS
    assert 'overrides' not in GOVERNED_PATHS and 'overrides' not in DOCS_SITE_SHARED_PATHS, (
        "a site's own extra override lives in overrides/ too: govern the two files, not the dir")


def test_a_sites_own_extra_override_is_not_drift(tmp_path, docs_upstream):
    """Material has one custom_dir; a partial of the site's own must not fail docs CI."""
    local_root = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'])
    write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])
    (local_root / 'overrides' / 'partials' / 'site-extra.html').write_text('x\n', encoding='utf-8')

    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 0


def test_docs_site_mode_names_an_unmapped_profile_stylesheet(tmp_path, docs_upstream, capsys):
    """A TEMPLATE_REF.md from before #135 maps nothing: say so, with the line to add."""
    css_up = '.agents/templates/docs-profiles/liferay/liferay-blue.css'
    local_root = adopter_with_docs_files(
        tmp_path / 'local', docs_upstream['path'],
        at={css_up: 'docs/assets/stylesheets/liferay-blue.css'})
    write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])

    assert main(['--root', str(local_root), '--docs-site']) == 0
    assert f"- `docs/assets/stylesheets/liferay-blue.css` ← `{css_up}`" in capsys.readouterr().out


def test_the_copy_direction_is_only_given_for_shared_files(tmp_path, upstream_repo, capsys):
    """AGENTS.md is customised by bootstrap: never tell an adopter to overwrite it."""
    local_root = tmp_path / 'local'
    (local_root / '.agents' / 'skills' / 'unit-testing').mkdir(parents=True)
    (local_root / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').write_bytes(
        (upstream_repo['path'] / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').read_bytes())
    (local_root / 'AGENTS.md').write_text('# Agents\n\ncustomised\n', encoding='utf-8')
    write_reference_file(local_root, upstream_repo['url'], upstream_repo['head_commit'])

    assert main(['--root', str(local_root)]) == 0
    out = capsys.readouterr().out
    assert 'AGENTS.md' in out and 'copy the file FROM' not in out


# --------------------------------------------------------------------------------------
# #141: lessons from the first adopter migration (lfr-tunnel#2408)
# --------------------------------------------------------------------------------------

CSS_UPSTREAM = '.agents/templates/docs-profiles/liferay/liferay-blue.css'
CSS_LOCAL = 'docs/assets/stylesheets/liferay-blue.css'


def test_docs_site_mode_compares_the_drift_checker_itself(tmp_path, docs_upstream, capsys):
    """It is copied verbatim, so an edit to it must fail docs CI like any other shared file."""
    assert 'scripts/check_template_drift.py' in DOCS_SITE_SHARED_PATHS
    local_root = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'])
    write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])
    (local_root / 'scripts' / 'check_template_drift.py').write_text('# patched\n',
                                                                    encoding='utf-8')

    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 2
    out = capsys.readouterr().out
    assert 'scripts/check_template_drift.py' in out
    assert DIRECTION_MESSAGE.format(repo_url=docs_upstream['url']) in out


def test_the_drift_checker_runs_beside_a_diverged_check_docs_review(tmp_path):
    """A shared file must not need a non-shared one patched to import. lfr-tunnel keeps its
    own check_docs_review.py, without FOOTER_REGEX, and had to add the name by hand (#141)."""
    import json
    from check_docs_review import FOOTER_REGEX, IGNORE_DIRS

    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (scripts / 'check_template_drift.py').write_bytes(
        (REPO_ROOT / 'scripts' / 'check_template_drift.py').read_bytes())
    (scripts / 'check_docs_review.py').write_text(
        '"""A diverged copy, with its own names."""\n'
        'import re\nFOOTER_PATTERN = re.compile(r"Last Updated")\n', encoding='utf-8')
    probe = ('import json, check_template_drift as m; '
             'print(json.dumps([m.FOOTER_REGEX.pattern, sorted(m.IGNORE_DIRS)]))')
    result = subprocess.run([sys.executable, '-c', probe], cwd=scripts,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    # The fallback is the template's own definition, word for word.
    assert json.loads(result.stdout) == [FOOTER_REGEX.pattern, sorted(IGNORE_DIRS)]


def test_docs_site_fail_on_drift_fails_an_unmapped_profile_stylesheet(
        tmp_path, docs_upstream, capsys):
    """A deleted mapping must not leave the shared stylesheet uncompared on a green run."""
    local_root = adopter_with_docs_files(tmp_path / 'local', docs_upstream['path'],
                                         at={CSS_UPSTREAM: CSS_LOCAL})
    write_reference_file(local_root, docs_upstream['url'], docs_upstream['commit'])

    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 3
    captured = capsys.readouterr()
    assert f"- `{CSS_LOCAL}` ← `{CSS_UPSTREAM}`" in captured.out
    assert 'not compared' in captured.err


def test_the_copy_direction_ignores_upstream_only_profile_files(tmp_path, docs_upstream, capsys):
    """The profile's about.md and site.yml are upstream only, and are not shared files: with
    only a customised AGENTS.md differing, no copy-FROM direction is printed (lfr-tunnel#2408)."""
    origin = docs_upstream['path']
    for rel, body in (('.agents/templates/docs-profiles/liferay/about.md', '# About\n'),
                      ('.agents/templates/docs-profiles/liferay/site.yml', 'extra: {}\n'),
                      ('AGENTS.md', '# Agents\n\nupstream\n')):
        (origin / rel).write_text(body, encoding='utf-8')
    run_git(['add', '.'], origin)
    run_git(['commit', '--quiet', '-m', 'profile files'], origin)
    local_root = adopter_with_docs_files(tmp_path / 'local', origin,
                                         skip=('.agents/templates/docs-profiles/liferay/about.md',
                                               '.agents/templates/docs-profiles/liferay/site.yml'))
    (local_root / 'AGENTS.md').write_text('# Agents\n\ncustomised\n', encoding='utf-8')
    write_reference_file(local_root, docs_upstream['url'], 'unknown')

    assert main(['--root', str(local_root)]) == 0
    out = capsys.readouterr().out
    assert 'about.md' in out and 'AGENTS.md' in out
    assert 'copy the file FROM' not in out

    # The control: the shared stylesheet differing does get the direction.
    (local_root / CSS_UPSTREAM).write_text(':root { --edited: 1; }\n', encoding='utf-8')
    assert main(['--root', str(local_root)]) == 0
    assert 'copy the file FROM' in capsys.readouterr().out


def test_a_customised_profile_seed_is_not_a_shared_file():
    from check_template_drift import is_shared_file
    assert is_shared_file(CSS_UPSTREAM)
    assert not is_shared_file('.agents/templates/docs-profiles/liferay/site.yml')
    assert not is_shared_file('.agents/templates/docs-profiles/liferay/about.md')


def _adopter_at_baseline(tmp_path, upstream_repo):
    """An adopter holding the upstream's BASELINE content, stamped at the baseline commit."""
    local_root = tmp_path / 'local'
    run_git(['checkout', '--quiet', upstream_repo['baseline_commit']], upstream_repo['path'])
    try:
        for rel in ('.agents/skills/unit-testing/SKILL.md', 'AGENTS.md'):
            (local_root / rel).parent.mkdir(parents=True, exist_ok=True)
            (local_root / rel).write_bytes((upstream_repo['path'] / rel).read_bytes())
    finally:
        run_git(['checkout', '--quiet', 'main'], upstream_repo['path'])
    reference = write_reference_file(local_root, upstream_repo['url'],
                                     upstream_repo['baseline_commit'])
    return local_root, reference


def test_against_recorded_ignores_a_template_merge(tmp_path, upstream_repo, capsys):
    """A merge to the template's main must not turn an untouched adopter red (#141)."""
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)

    assert main(['--root', str(local_root), '--fail-on-drift']) == 2, (
        "the control: against HEAD, the template's later commit is drift")
    capsys.readouterr()
    assert main(['--root', str(local_root), '--fail-on-drift', '--against-recorded']) == 0
    out = capsys.readouterr().out
    assert 'vs the recorded ref' in out and 'No drift' in out


def test_against_recorded_still_fails_a_local_edit(tmp_path, upstream_repo, capsys):
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    (local_root / 'AGENTS.md').write_text('# Agents\n\nedited here\n', encoding='utf-8')

    assert main(['--root', str(local_root), '--fail-on-drift', '--against-recorded']) == 2
    assert 'AGENTS.md' in capsys.readouterr().out


@pytest.mark.parametrize('recorded', [UNKNOWN_STAMP_VALUE, 'abc1234'])
def test_against_recorded_fails_when_the_recorded_commit_is_unusable(
        tmp_path, upstream_repo, capsys, recorded):
    """No baseline to compare against is "nothing compared", not a pass."""
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    write_reference_file(local_root, upstream_repo['url'], recorded)

    assert main(['--root', str(local_root), '--against-recorded']) == 3
    assert '--update-stamp' in capsys.readouterr().err


def test_against_recorded_refuses_to_move_the_stamp(tmp_path, upstream_repo, capsys):
    """The stamp records a comparison against HEAD; this mode never makes one."""
    local_root, reference = _adopter_at_baseline(tmp_path, upstream_repo)
    before = reference.read_text(encoding='utf-8')

    with pytest.raises(SystemExit):
        main(['--root', str(local_root), '--against-recorded', '--update-stamp'])
    assert 'not allowed with' in capsys.readouterr().err
    assert reference.read_text(encoding='utf-8') == before


def test_the_drift_checker_names_the_template_as_canonical():
    """Now a shared file, its header must send a downstream editor upstream, like the others."""
    header = (REPO_ROOT / 'scripts' / 'check_template_drift.py').read_text(encoding='utf-8')[:1500]
    assert 'SHARED FILE' in header and 'Never edit a copy' in header
    assert 'peterrichards-lr/ai-agent-template' in header
