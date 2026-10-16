"""
test_drift_release_notice.py - --against-recorded in PR CI: a template merge cannot fail it

Five template merges in one morning turned every adopter's docs PR red with no local change,
because PR CI compared the shared files against upstream HEAD. PR CI now runs
`--docs-site --fail-on-drift --against-recorded`, as the deploy does:

- a local edit to a shared file still fails;
- an `unknown` stamp (a fresh project) falls back to HEAD, rather than exiting 3;
- a newer upstream release than the stamp is NOT a failure, but is named, with the shared
  files it changes, so the sync is not missed.

A dedicated module beside tests/test_template_drift.py, whose git fixtures it reuses.
"""

import pytest

from test_template_drift import (  # noqa: F401  (upstream_repo is a fixture)
    _adopter_at_baseline, main, run_git, upstream_repo, write_reference_file)

SKILL = '.agents/skills/unit-testing/SKILL.md'


def _release(upstream_repo, tag='v1.1.0'):
    """Tag upstream's HEAD, which changed SKILL since the v1.0.0 baseline."""
    run_git(['tag', tag], upstream_repo['path'])


def test_a_newer_release_is_named_with_the_files_it_changes_and_exits_0(
        tmp_path, upstream_repo, capsys):
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    _release(upstream_repo)
    code = main(['--root', str(local_root), '--against-recorded', '--fail-on-drift'])
    out = capsys.readouterr().out
    assert code == 0, out
    assert 'newer release, v1.1.0 (this repository records v1.0.0)' in out, out
    assert f'   - {SKILL}' in out and 'It changes 1 of the shared files' in out, out


def test_a_local_edit_still_fails_with_a_newer_release_waiting(tmp_path, upstream_repo, capsys):
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    _release(upstream_repo)
    (local_root / 'AGENTS.md').write_text('# Agents\n\nedited here\n', encoding='utf-8')
    assert main(['--root', str(local_root), '--against-recorded', '--fail-on-drift']) == 2


def test_no_newer_release_no_notice(tmp_path, upstream_repo, capsys):
    """An untagged merge upstream: nothing to sync to yet, and nothing said."""
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    assert main(['--root', str(local_root), '--against-recorded', '--fail-on-drift']) == 0
    assert 'newer release' not in capsys.readouterr().out


def test_a_newer_release_that_changes_none_of_the_compared_files_says_so(
        tmp_path, upstream_repo, capsys):
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    _release(upstream_repo)
    code = main(['--root', str(local_root), '--against-recorded', '--fail-on-drift',
                 '--path', 'AGENTS.md'])
    out = capsys.readouterr().out
    assert code == 0, out
    assert 'changes none of the shared files compared here' in out, out


def test_head_mode_prints_no_release_notice(tmp_path, upstream_repo, capsys):
    """The notice belongs to --against-recorded; HEAD mode already reports upstream commits."""
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    _release(upstream_repo)
    main(['--root', str(local_root)])
    assert 'newer release' not in capsys.readouterr().out


@pytest.mark.parametrize('version', ['unknown', 'main', 'v1.0'])
def test_a_stamp_version_that_is_not_a_release_gives_no_notice(
        tmp_path, upstream_repo, capsys, version):
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    _release(upstream_repo)
    write_reference_file(local_root, upstream_repo['url'], upstream_repo['baseline_commit'],
                         version=version)
    assert main(['--root', str(local_root), '--against-recorded', '--fail-on-drift']) == 0
    assert 'newer release' not in capsys.readouterr().out


def test_an_unknown_stamp_falls_back_to_head(tmp_path, upstream_repo, capsys):
    """A fresh project: compared against HEAD, so its baseline-era copy is drift there."""
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    write_reference_file(local_root, upstream_repo['url'], 'unknown', version='unknown')
    code = main(['--root', str(local_root), '--against-recorded', '--fail-on-drift'])
    out = capsys.readouterr().out
    assert 'records no commit yet' in out and 'against upstream HEAD' in out, out
    assert code == 2, "the fallback compares against HEAD, where the copy is out of date"


def test_an_unknown_stamp_matching_head_passes(tmp_path, upstream_repo, capsys):
    local_root, _ = _adopter_at_baseline(tmp_path, upstream_repo)
    (local_root / SKILL).write_bytes((upstream_repo['path'] / SKILL).read_bytes())
    write_reference_file(local_root, upstream_repo['url'], 'unknown', version='unknown')
    assert main(['--root', str(local_root), '--against-recorded', '--fail-on-drift']) == 0
