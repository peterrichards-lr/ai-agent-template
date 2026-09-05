"""
test_release.py - Release Automation Contract

Covers scripts/release.py and .github/workflows/release.yml: the tooling that turns
.agents/skills/release-management/SKILL.md from prose into a gate.

Deliberately a dedicated module rather than an addition to
tests/test_template_scripts.py: release automation is its own surface -- version
arithmetic, Conventional Commit parsing, the issue-closure audit, changelog
rendering and the publish workflow -- and it evolves with the release policy rather
than with the template bootstrap scripts. pytest auto-discovers tests/test_*.py.

The highest-value assertions here are the ones covering the issue-closure audit
(SKILL.md rule 3) and the refusal to write or tag when it fails. That is the rule a
human is most likely to skip, so it is the rule most worth pinning mechanically.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT_DIR / 'scripts'
WORKFLOWS_DIR = ROOT_DIR / '.github' / 'workflows'
RELEASE_WORKFLOW = WORKFLOWS_DIR / 'release.yml'
RELEASE_SKILL = ROOT_DIR / '.agents' / 'skills' / 'release-management' / 'SKILL.md'

sys.path.insert(0, str(SCRIPTS_DIR))

from release import (  # noqa: E402
    EXIT_AUDIT_FAILED,
    EXIT_OK,
    EXIT_REFUSED,
    CommitEntry,
    ReleaseError,
    apply_changelog_release,
    audit_issue_closures,
    bump_version,
    classify_bump,
    collect_referenced_issues,
    extract_changelog_section,
    format_version_tag,
    main,
    parse_commit,
    parse_version_tag,
    render_changelog_entries,
)

MINIMAL_CHANGELOG = """# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- A curated entry a human wrote by hand (#46).

### Fixed

- _Nothing yet._

[Unreleased]: https://github.com/acme/widget/compare/main...HEAD
"""


def make_commit(subject: str, body: str = '', sha: str = 'abc1234') -> CommitEntry:
    return parse_commit(sha, subject, body)


# ---------------------------------------------------------------------------
# Semantic version arithmetic
# ---------------------------------------------------------------------------

def test_parse_version_tag_accepts_the_repository_tag_format():
    assert parse_version_tag('v1.4.0') == (1, 4, 0)
    # `git describe` output is the only producer, but tolerate a missing 'v'.
    assert parse_version_tag('1.4.0') == (1, 4, 0)
    assert format_version_tag((1, 5, 0)) == 'v1.5.0'


def test_parse_version_tag_rejects_anything_that_is_not_semver():
    for bad in ('v1.4', 'release-1.4.0', 'v1.4.0-rc1', '', 'vX.Y.Z'):
        with pytest.raises(ReleaseError):
            parse_version_tag(bad)


def test_bump_version_applies_semver_reset_rules():
    assert bump_version('v1.4.0', 'patch') == 'v1.4.1'
    assert bump_version('v1.4.0', 'minor') == 'v1.5.0'
    assert bump_version('v1.4.3', 'minor') == 'v1.5.0'
    assert bump_version('v1.4.3', 'major') == 'v2.0.0'


def test_bump_version_rejects_an_unknown_level():
    with pytest.raises(ReleaseError):
        bump_version('v1.4.0', 'epic')


# ---------------------------------------------------------------------------
# Conventional Commit parsing
# ---------------------------------------------------------------------------

def test_parse_commit_extracts_type_scope_and_pull_request_number():
    entry = make_commit('feat(template-sync): ship the drift checker (#95)')

    assert entry.is_conventional
    assert entry.type == 'feat'
    assert entry.scope == 'template-sync'
    assert entry.breaking is False
    assert entry.pull_request == 95
    assert entry.description == 'ship the drift checker'


def test_parse_commit_strips_a_closing_reference_out_of_the_subject():
    """#76's real subject carries '(Closes #52)' before the PR number."""
    entry = make_commit(
        'feat(ci): add PR scope-sprawl CI gate and coding-standards guardrail '
        '(Closes #52) (#76)'
    )

    assert entry.pull_request == 76
    assert entry.issues == (52,)
    assert entry.description == 'add PR scope-sprawl CI gate and coding-standards guardrail'


def test_parse_commit_collects_closing_references_from_the_body():
    entry = make_commit(
        'feat(bootstrap): add verification and dry-run (#89)',
        'Some prose.\n\nCloses #29\nCloses #40\nCloses #29\n',
    )

    assert entry.issues == (29, 40)


def test_parse_commit_marks_non_conventional_subjects():
    """Dependabot merge commits are in the real v1.4.0..HEAD range."""
    entry = make_commit('Merge pull request #25 from acme/dependabot/pip/pytest-9.1.1')

    assert entry.is_conventional is False
    assert entry.type == ''


def test_parse_commit_detects_both_breaking_change_markers():
    assert make_commit('feat(api)!: drop the -y flag').breaking is True
    assert make_commit(
        'refactor(api): rework the flags',
        'BREAKING CHANGE: -y is gone.\n',
    ).breaking is True


# ---------------------------------------------------------------------------
# Bump classification -- propose, never assume
# ---------------------------------------------------------------------------

def test_classify_bump_maps_conventional_types_to_semver_levels():
    assert classify_bump([make_commit('fix(ci): repair the gate (#67)')])[0] == 'patch'
    assert classify_bump([make_commit('feat(ci): add a gate (#67)')])[0] == 'minor'
    assert classify_bump([make_commit('feat(ci)!: replace the gate (#67)')])[0] == 'major'


def test_classify_bump_takes_the_highest_level_in_the_range():
    commits = [
        make_commit('docs: fix a typo (#64)'),
        make_commit('fix(ci): repair the gate (#67)'),
        make_commit('feat(ci): add a gate (#68)'),
    ]

    level, reason = classify_bump(commits)

    assert level == 'minor'
    assert 'feat' in reason


def test_classify_bump_defaults_to_patch_for_a_range_with_no_feat_or_breaking():
    commits = [make_commit('docs: retitle a section (#64)'),
               make_commit('Merge pull request #25 from acme/dependabot')]

    assert classify_bump(commits)[0] == 'patch'


def test_classify_bump_refuses_an_empty_range():
    with pytest.raises(ReleaseError):
        classify_bump([])


# ---------------------------------------------------------------------------
# The issue-closure audit (SKILL.md rule 3)
# ---------------------------------------------------------------------------

def test_collect_referenced_issues_deduplicates_across_commits():
    commits = [
        make_commit('feat(a): one (#89)', 'Closes #29\nCloses #40\n'),
        make_commit('feat(b): two (#90)', 'Closes #29\n'),
        make_commit('fix(c): three (#91)', 'Fixes #12\n'),
    ]

    assert collect_referenced_issues(commits) == (12, 29, 40)


def test_audit_issue_closures_passes_when_every_referenced_issue_is_closed():
    audit = audit_issue_closures((29, 40), lambda number: 'CLOSED')

    assert audit.ok is True
    assert audit.open_issues == ()
    assert audit.unverified == ()


def test_audit_issue_closures_refuses_when_a_referenced_issue_is_still_open():
    """A squash-merge that dropped a 'Closes #N' must stop the release."""
    audit = audit_issue_closures((29, 40), lambda number: 'OPEN' if number == 40 else 'CLOSED')

    assert audit.ok is False
    assert audit.open_issues == (40,)


def test_audit_issue_closures_refuses_when_an_issue_state_cannot_be_verified():
    """Verify, don't assume: an unreachable gh is a refusal, not a pass."""
    audit = audit_issue_closures((29,), lambda number: None)

    assert audit.ok is False
    assert audit.unverified == (29,)


def test_audit_issue_closures_records_an_explicit_skip_as_not_verified():
    audit = audit_issue_closures((29,), lambda number: 'CLOSED', skipped=True)

    assert audit.skipped is True
    assert audit.ok is True
    assert audit.closed == ()


# ---------------------------------------------------------------------------
# Changelog rendering
# ---------------------------------------------------------------------------

def test_render_changelog_entries_groups_by_keep_a_changelog_category():
    commits = [
        make_commit('feat(docs): add the site (#93)'),
        make_commit('fix(bootstrap): require --name (#92)'),
        make_commit('docs: retitle a section (#64)'),
    ]

    rendered = render_changelog_entries(commits)

    assert '### Added' in rendered
    assert '### Fixed' in rendered
    assert '### Changed' in rendered
    assert rendered.index('### Added') < rendered.index('### Changed') < rendered.index('### Fixed')
    assert '- **docs**: add the site (#93)' in rendered
    assert '- **bootstrap**: require --name (#92)' in rendered


def test_render_changelog_entries_links_the_issue_alongside_the_pull_request():
    rendered = render_changelog_entries(
        [make_commit('feat(ci): add a gate (#76)', 'Closes #52\n')])

    assert '(#76, #52)' in rendered


def test_render_changelog_entries_marks_breaking_changes():
    rendered = render_changelog_entries([make_commit('feat(api)!: drop the -y flag (#90)')])

    assert '**Breaking**' in rendered


def test_render_changelog_entries_omits_non_conventional_commits():
    rendered = render_changelog_entries([
        make_commit('feat(a): keep me (#1)'),
        make_commit('Merge pull request #25 from acme/dependabot'),
    ])

    assert 'Merge pull request' not in rendered


def test_apply_changelog_release_promotes_unreleased_into_a_version_section():
    updated = apply_changelog_release(
        MINIMAL_CHANGELOG,
        version='v1.5.0',
        release_date='2026-09-05',
        commits=[make_commit('feat(docs): add the site (#93)')],
    )

    assert '## [1.5.0] - 2026-09-05' in updated
    # The curated entry moves down into the released section, not into a second copy.
    assert updated.count('A curated entry a human wrote by hand (#46).') == 1
    assert updated.index('## [Unreleased]') < updated.index('## [1.5.0]')
    assert updated.index('## [1.5.0]') < updated.index('A curated entry a human wrote by hand')
    assert '- **docs**: add the site (#93)' in updated


def test_apply_changelog_release_emits_one_heading_per_category():
    """Curated and generated entries in the same category share one `### Added`.

    Regression: the first real run against v1.4.0..HEAD rendered the curated block and
    the generated block back to back, producing two `### Added` headings inside one
    release section. MD024 is disabled in .markdownlint-cli2.jsonc, so no linter saw it.
    """
    updated = apply_changelog_release(
        MINIMAL_CHANGELOG,
        version='v1.5.0',
        release_date='2026-09-05',
        commits=[make_commit('feat(docs): add the site (#93)'),
                 make_commit('fix(bootstrap): require --name (#92)')],
    )

    section = updated.split('## [1.5.0]')[1]
    assert section.count('### Added') == 1
    assert section.count('### Fixed') == 1
    # The curated entry and the generated one sit under the same heading.
    assert section.index('A curated entry') < section.index('add the site (#93)')
    assert '### Fixed' not in section[:section.index('add the site (#93)')]


def test_apply_changelog_release_does_not_duplicate_a_curated_entry():
    """A commit already described by hand under [Unreleased] is not restated."""
    updated = apply_changelog_release(
        MINIMAL_CHANGELOG,
        version='v1.5.0',
        release_date='2026-09-05',
        commits=[make_commit('feat(runner): add the Makefile task runner (#46)')],
    )

    assert 'add the Makefile task runner' not in updated
    assert updated.count('(#46)') == 1


def test_apply_changelog_release_resets_unreleased_and_rewrites_the_link_definitions():
    updated = apply_changelog_release(
        MINIMAL_CHANGELOG,
        version='v1.5.0',
        release_date='2026-09-05',
        commits=[make_commit('feat(docs): add the site (#93)')],
    )

    unreleased_body = updated.split('## [Unreleased]')[1].split('## [1.5.0]')[0]
    assert '_Nothing yet._' in unreleased_body
    assert '(#93)' not in unreleased_body

    assert '[Unreleased]: https://github.com/acme/widget/compare/v1.5.0...HEAD' in updated
    assert '[1.5.0]: https://github.com/acme/widget/releases/tag/v1.5.0' in updated


def test_apply_changelog_release_leaves_a_blank_line_before_the_trailing_block():
    """Regression: the real CHANGELOG.md ends with a commented example block.

    The first real run against v1.4.0..HEAD glued `<!--` straight onto the last
    bullet, where a Markdown parser can read the comment as a continuation of that
    list item. MD032 is disabled in .markdownlint-cli2.jsonc, so no linter saw it.
    """
    changelog_with_trailing_block = MINIMAL_CHANGELOG.replace(
        '[Unreleased]: ',
        '<!--\nExample of a released version:\n\n## [1.0.0] - 2026-01-31\n-->\n\n[Unreleased]: ',
    )

    updated = apply_changelog_release(
        changelog_with_trailing_block,
        version='v1.5.0',
        release_date='2026-09-05',
        commits=[make_commit('feat(docs): add the site (#93)')],
    )

    assert '(#93)\n\n<!--' in updated, (
        "The generated section must end with a blank line before the trailing block"
    )


def test_apply_changelog_release_refuses_a_changelog_with_no_unreleased_heading():
    with pytest.raises(ReleaseError):
        apply_changelog_release(
            '# Changelog\n\nNothing here.\n',
            version='v1.5.0',
            release_date='2026-09-05',
            commits=[make_commit('feat(docs): add the site (#93)')],
        )


def test_extract_changelog_section_returns_only_that_versions_body():
    changelog = (
        '# Changelog\n\n'
        '## [Unreleased]\n\n_Nothing yet._\n\n'
        '## [1.5.0] - 2026-09-05\n\n### Added\n\n- New thing (#93).\n\n'
        '## [1.4.0] - 2026-08-01\n\n### Added\n\n- Older thing (#1).\n'
    )

    section = extract_changelog_section(changelog, 'v1.5.0')

    assert '- New thing (#93).' in section
    assert 'Older thing' not in section
    assert 'Unreleased' not in section


def test_extract_changelog_section_raises_for_a_version_that_was_never_written():
    with pytest.raises(ReleaseError):
        extract_changelog_section('# Changelog\n\n## [Unreleased]\n\n_Nothing yet._\n', 'v9.9.9')


# ---------------------------------------------------------------------------
# End-to-end against a real git repository
# ---------------------------------------------------------------------------

def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ['git', '-C', str(repo)] + list(args),
        capture_output=True, text=True, check=True, timeout=60,
    )
    return result.stdout.strip()


@pytest.fixture()
def release_repo(tmp_path: Path) -> Path:
    """A throwaway repository with one tag and two Conventional Commits after it."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '--quiet', '--initial-branch', 'main')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'commit.gpgsign', 'false')

    (repo / 'CHANGELOG.md').write_text(MINIMAL_CHANGELOG, encoding='utf-8')
    git(repo, 'add', 'CHANGELOG.md')
    git(repo, 'commit', '--quiet', '-m', 'chore: seed the changelog')
    git(repo, 'tag', '-a', 'v1.4.0', '-m', 'v1.4.0')

    (repo / 'feature.txt').write_text('one\n', encoding='utf-8')
    git(repo, 'add', 'feature.txt')
    git(repo, 'commit', '--quiet', '-m', 'feat(docs): add the site (#93)\n\nCloses #40\n')

    (repo / 'fix.txt').write_text('two\n', encoding='utf-8')
    git(repo, 'add', 'fix.txt')
    git(repo, 'commit', '--quiet', '-m', 'fix(bootstrap): require --name (#92)')

    return repo


def run_release(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / 'release.py'), '--root', str(repo)] + list(args),
        capture_output=True, text=True, timeout=120,
    )


def test_dry_run_proposes_the_next_version_and_writes_nothing(release_repo: Path):
    changelog = release_repo / 'CHANGELOG.md'
    before = changelog.read_text(encoding='utf-8')

    result = run_release(release_repo, '--dry-run', '--skip-issue-audit')

    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert 'v1.4.0' in result.stdout
    assert 'v1.5.0' in result.stdout
    assert changelog.read_text(encoding='utf-8') == before, "--dry-run must touch nothing"
    assert git(release_repo, 'tag', '-l') == 'v1.4.0', "--dry-run must not create a tag"


def test_dry_run_honours_an_explicit_bump_override(release_repo: Path):
    result = run_release(release_repo, '--dry-run', '--skip-issue-audit', '--bump', 'major')

    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert 'v2.0.0' in result.stdout


def test_a_failed_issue_audit_refuses_to_write_the_changelog(release_repo: Path, monkeypatch):
    """The range references #40; a stub gh reporting it OPEN must stop the release."""
    fake_bin = release_repo.parent / 'fakebin'
    fake_bin.mkdir()
    gh_stub = fake_bin / 'gh'
    gh_stub.write_text(
        '#!/bin/sh\n'
        'echo \'{"number": 40, "state": "OPEN", "title": "still open"}\'\n',
        encoding='utf-8',
    )
    gh_stub.chmod(0o755)

    changelog = release_repo / 'CHANGELOG.md'
    before = changelog.read_text(encoding='utf-8')

    env_path = f"{fake_bin}:{subprocess.os.environ.get('PATH', '')}"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / 'release.py'), '--root', str(release_repo)],
        capture_output=True, text=True, timeout=120,
        env={**subprocess.os.environ, 'PATH': env_path},
    )

    assert result.returncode == EXIT_AUDIT_FAILED, result.stdout + result.stderr
    assert '#40' in result.stdout + result.stderr
    assert changelog.read_text(encoding='utf-8') == before, (
        "A failed issue-closure audit must not leave a half-written changelog"
    )


def test_prepare_writes_the_changelog_but_never_tags(release_repo: Path):
    result = run_release(release_repo, '--skip-issue-audit')

    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    changelog = (release_repo / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert '## [1.5.0]' in changelog
    assert '- **docs**: add the site (#93, #40)' in changelog
    assert git(release_repo, 'tag', '-l') == 'v1.4.0', (
        "Preparing the changelog must not tag: tagging is a separate, confirmed step"
    )


def test_tagging_refuses_without_confirmation_when_no_human_is_present(release_repo: Path):
    run_release(release_repo, '--skip-issue-audit')
    git(release_repo, 'add', 'CHANGELOG.md')
    git(release_repo, 'commit', '--quiet', '-m', 'docs(release): prepare v1.5.0')

    result = run_release(release_repo, '--tag', '--skip-issue-audit')

    assert result.returncode == EXIT_REFUSED, result.stdout + result.stderr
    assert git(release_repo, 'tag', '-l') == 'v1.4.0'


def test_tagging_refuses_while_the_changelog_is_uncommitted(release_repo: Path):
    run_release(release_repo, '--skip-issue-audit')

    result = run_release(release_repo, '--tag', '--yes', '--skip-issue-audit')

    assert result.returncode == EXIT_REFUSED, result.stdout + result.stderr
    assert git(release_repo, 'tag', '-l') == 'v1.4.0'


def test_confirmed_tagging_creates_an_annotated_tag_and_does_not_push(release_repo: Path):
    run_release(release_repo, '--skip-issue-audit')
    git(release_repo, 'add', 'CHANGELOG.md')
    git(release_repo, 'commit', '--quiet', '-m', 'docs(release): prepare v1.5.0')

    result = run_release(release_repo, '--tag', '--yes', '--skip-issue-audit')

    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert 'v1.5.0' in git(release_repo, 'tag', '-l').split()
    assert git(release_repo, 'cat-file', '-t', 'v1.5.0') == 'tag', (
        "Version tags must be annotated, not lightweight"
    )
    assert 'git push origin v1.5.0' in result.stdout, (
        "The push is left to a human; the script must print the exact command"
    )
    # The annotation must come from the committed changelog, not from a fresh
    # re-derivation: by this point [Unreleased] has already been emptied, so
    # re-deriving would annotate the tag with a near-empty section.
    annotation = git(release_repo, 'tag', '-l', '--format=%(contents)', 'v1.5.0')
    assert '- **docs**: add the site (#93, #40)' in annotation
    assert 'A curated entry a human wrote by hand (#46).' in annotation


def test_extract_notes_prints_the_section_the_release_workflow_publishes(release_repo: Path):
    run_release(release_repo, '--skip-issue-audit')

    result = run_release(release_repo, '--extract-notes', 'v1.5.0')

    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert '- **docs**: add the site (#93, #40)' in result.stdout
    assert 'Unreleased' not in result.stdout


def test_extract_notes_fails_for_a_version_with_no_changelog_section(release_repo: Path):
    result = run_release(release_repo, '--extract-notes', 'v9.9.9')

    assert result.returncode != EXIT_OK
    assert 'v9.9.9' in result.stdout + result.stderr


def test_release_refuses_when_the_range_is_empty(release_repo: Path):
    git(release_repo, 'tag', '-a', 'v1.5.0', '-m', 'v1.5.0')

    result = run_release(release_repo, '--dry-run', '--skip-issue-audit')

    assert result.returncode == EXIT_REFUSED, result.stdout + result.stderr


def test_main_is_importable_and_returns_an_exit_code(release_repo: Path):
    assert main(['--root', str(release_repo), '--dry-run', '--skip-issue-audit']) == EXIT_OK


# ---------------------------------------------------------------------------
# .github/workflows/release.yml
# ---------------------------------------------------------------------------

def load_workflow(path: Path) -> dict:
    """Parse a workflow, tolerating YAML 1.1 coercion of the `on:` key to True."""
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if True in data and 'on' not in data:
        data['on'] = data.pop(True)
    return data


def test_release_workflow_triggers_only_on_version_tag_pushes():
    assert RELEASE_WORKFLOW.exists(), "Expected .github/workflows/release.yml to exist"

    triggers = load_workflow(RELEASE_WORKFLOW).get('on', {})

    assert set(triggers) == {'push'}, (
        "release.yml must run on tag pushes only; a pull_request trigger would try to "
        "publish a release for every PR"
    )
    assert triggers['push'].get('tags') == ['v*']
    assert 'branches' not in triggers['push']


def test_release_workflow_requests_only_the_permission_it_needs():
    workflow = load_workflow(RELEASE_WORKFLOW)

    assert workflow.get('permissions') == {'contents': 'write'}, (
        "Publishing a release needs contents: write and nothing else"
    )


def test_release_workflow_cancels_superseded_runs_like_other_non_required_workflows():
    concurrency = load_workflow(RELEASE_WORKFLOW).get('concurrency', {})

    assert concurrency.get('cancel-in-progress') is True, (
        "release.yml supplies no required status check, so it follows the "
        "security-scan.yml convention rather than ci.yml's"
    )


def test_release_workflow_is_not_a_required_status_check():
    """It runs after merge, so requiring it would deadlock protect-main-branch.json."""
    import json

    ruleset = json.loads(
        (ROOT_DIR / '.github' / 'rulesets' / 'protect-main-branch.json').read_text(encoding='utf-8'))

    contexts = [
        check.get('context')
        for rule in ruleset.get('rules', [])
        if rule.get('type') == 'required_status_checks'
        for check in rule.get('parameters', {}).get('required_status_checks', [])
    ]
    job_names = [
        job.get('name', job_id)
        for job_id, job in load_workflow(RELEASE_WORKFLOW).get('jobs', {}).items()
    ]

    for name in job_names:
        assert name not in contexts, (
            f"release.yml job '{name}' must not be a required status check: it only "
            "runs on a tag push, so a pull request could never satisfy it"
        )


def test_release_workflow_verifies_the_tag_before_publishing():
    """A tag pushed at an arbitrary commit must not silently publish stale notes."""
    text = RELEASE_WORKFLOW.read_text(encoding='utf-8')

    assert 'github.ref_name' in text
    assert 'scripts/release.py --extract-notes' in text, (
        "The workflow must reuse the tested extractor rather than re-implementing "
        "changelog parsing in shell"
    )
    assert 'gh release create' in text
    assert '--verify-tag' in text, (
        "gh release create --verify-tag refuses to invent a tag that does not exist"
    )


def test_release_workflow_checks_out_full_history():
    """`git describe` and tag verification both need more than a shallow clone."""
    jobs = load_workflow(RELEASE_WORKFLOW).get('jobs', {})
    steps = [step for job in jobs.values() for step in job.get('steps', [])]

    checkout = [s for s in steps if str(s.get('uses', '')).startswith('actions/checkout@')]
    assert checkout, "release.yml must check out the repository"
    assert checkout[0].get('with', {}).get('fetch-depth') == 0


# ---------------------------------------------------------------------------
# Cross-references
# ---------------------------------------------------------------------------

def test_release_management_skill_points_at_the_automation():
    skill = RELEASE_SKILL.read_text(encoding='utf-8')

    assert 'scripts/release.py' in skill, (
        "The skill states the policy; it must name the tool that executes it"
    )
    assert '.github/workflows/release.yml' in skill
    assert '--dry-run' in skill
