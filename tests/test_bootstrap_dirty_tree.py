"""
test_bootstrap_dirty_tree.py - Git is bootstrap's backup (#184)

Bootstrap rewrites and deletes tracked files: the Makefile profile, ci.yml, and README and
CHANGELOG under --clean-template. On a committed tree `git restore .` undoes all of it; on a
tree with uncommitted edits those edits would be lost. So a real run refuses a dirty tree
unless --allow-dirty is passed, --dry-run reports the check without refusing, and a tree git
cannot see is warned about rather than assumed clean.

A dedicated module, so parallel bootstrap work does not conflict on one file. The isolated
clone and the run helper come from tests/test_bootstrap_cleanup.py.
"""

import subprocess
from pathlib import Path

from test_bootstrap_cleanup import (
    QUICKSTART_ARGS, fingerprint_tree, make_isolated_clone, run_bootstrap)


def commit_clone(project: Path, env: dict):
    """Turn the isolated clone into a committed git work tree, as a real clone is."""
    identity = ['-c', 'user.email=test@example.com', '-c', 'user.name=Test']
    for args in (['init', '-q'], ['add', '-A'], [*identity, 'commit', '-qm', 'template']):
        subprocess.run(['git', *args], cwd=project, env=env, check=True, capture_output=True)


def work_tree_fingerprint(project: Path) -> dict:
    """The tree minus .git/, which git changes on its own: in CI the commit in commit_clone
    left a background `.git/objects/maintenance.lock` appearing between the two snapshots."""
    return {rel: digest for rel, digest in fingerprint_tree(project).items()
            if rel != '.git' and not rel.startswith('.git/')}


def _dirty_clone(tmp_path):
    project, env = make_isolated_clone(tmp_path)
    commit_clone(project, env)
    makefile = project / 'Makefile'
    makefile.write_text(makefile.read_text(encoding='utf-8') + '# local edit\n', encoding='utf-8')
    return project, env


def test_bootstrap_refuses_a_tree_with_uncommitted_tracked_changes(tmp_path):
    project, env = _dirty_clone(tmp_path)
    before = work_tree_fingerprint(project)

    result = run_bootstrap(project, env, QUICKSTART_ARGS)

    assert result.returncode == 1
    assert 'uncommitted changes' in result.stderr and 'Makefile' in result.stderr
    assert '--allow-dirty' in result.stderr
    assert work_tree_fingerprint(project) == before, "a refused run must not touch the tree"


def test_allow_dirty_runs_on_a_tree_with_uncommitted_changes(tmp_path):
    project, env = _dirty_clone(tmp_path)

    result = run_bootstrap(project, env, QUICKSTART_ARGS + ['--allow-dirty'])

    assert result.returncode == 0, result.stderr
    assert 'could overwrite' in result.stdout and 'Makefile' in result.stdout


def test_dry_run_reports_a_dirty_tree_without_refusing(tmp_path):
    project, env = _dirty_clone(tmp_path)

    result = run_bootstrap(project, env, QUICKSTART_ARGS + ['--dry-run'])

    assert result.returncode == 0, result.stderr
    assert 'could overwrite' in result.stdout


def test_a_committed_tree_is_reported_as_reversible(tmp_path):
    project, env = make_isolated_clone(tmp_path)
    commit_clone(project, env)

    result = run_bootstrap(project, env, QUICKSTART_ARGS)

    assert result.returncode == 0, result.stderr
    assert 'undo bootstrap with `git restore .`' in result.stdout


def test_a_tree_outside_git_is_warned_about_not_assumed_clean(tmp_path):
    """The isolated clone copies no .git, so git cannot vouch for it."""
    project, env = make_isolated_clone(tmp_path)
    assert not (project / '.git').exists()

    result = run_bootstrap(project, env, QUICKSTART_ARGS)

    assert result.returncode == 0, result.stderr
    assert 'not a git work tree' in result.stdout
