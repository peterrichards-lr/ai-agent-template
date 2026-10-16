"""
test_docs_workflow_drift.py - The shipped docs workflow: PR CI and the deploy

`.github/workflows/docs.yml` is PR CI on a pull request and the deploy on a push to main.
Both run one drift command, `check_template_drift.py --docs-site --fail-on-drift
--against-recorded`: a template merge cannot fail either, a local edit fails both, and the
script itself falls back to HEAD on an `unknown` stamp and prints a newer release as a notice
(tests/test_drift_release_notice.py).

Dependabot's pull requests skip the drift step, so a required docs check reports success
rather than pending, but still build the site and run the rendered check: dependency bumps are
what break rendering. A pull request never uploads or deploys.

The drift step's own shell is run, not a restatement of it. A `python` shim on PATH records
the drift check's arguments rather than cloning anything.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from test_template_drift import write_reference_file

ROOT_DIR = Path(__file__).parent.parent
DOCS_WORKFLOW = ROOT_DIR / '.github' / 'workflows' / 'docs.yml'
DEPENDABOT = ROOT_DIR / '.github' / 'dependabot.yml'
STEP_NAME = 'Check the shared docs files against the template'
URL = 'https://github.com/peterrichards-lr/ai-agent-template'
COMMAND = 'scripts/check_template_drift.py --docs-site --fail-on-drift --against-recorded'
NOT_DEPENDABOT = "${{ github.event.pull_request.user.login != 'dependabot[bot]' }}"
NOT_A_PR = "${{ github.event_name != 'pull_request' }}"


def _workflow():
    return yaml.safe_load(DOCS_WORKFLOW.read_text(encoding='utf-8'))


def _build_steps():
    return _workflow()['jobs']['build']['steps']


def _step(name):
    return next(step for step in _build_steps() if step.get('name') == name)


def _run_step(tmp_path, reference=None):
    """Run the drift step in a fake checkout; return (exit code, output, drift-check argv)."""
    project = tmp_path / 'project'
    (project / 'scripts').mkdir(parents=True)
    if reference is not None:
        (project / '.agents').mkdir()
        (project / '.agents' / 'TEMPLATE_REF.md').write_text(reference, encoding='utf-8')
    shim_dir = tmp_path / 'bin'
    shim_dir.mkdir()
    log = tmp_path / 'drift-calls.log'
    shim = shim_dir / 'python'
    shim.write_text(
        '#!/usr/bin/env bash\n'
        'if [ "$1" = "scripts/check_template_drift.py" ]; then\n'
        f'  echo "$*" >> "{log}"; exit 0\n'
        'fi\n'
        f'exec "{sys.executable}" "$@"\n', encoding='utf-8')
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, 'PATH': f'{shim_dir}{os.pathsep}{os.environ["PATH"]}'}
    result = subprocess.run(['bash', '-e', '-c', _step(STEP_NAME)['run']], cwd=project, env=env,
                            capture_output=True, text=True, check=False)
    calls = log.read_text(encoding='utf-8').splitlines() if log.exists() else []
    return result.returncode, result.stdout + result.stderr, calls


@pytest.mark.skipif(shutil.which('bash') is None, reason='needs bash')
@pytest.mark.parametrize('commit', ['25de5d1', 'unknown'])
def test_the_drift_step_always_compares_against_the_recorded_commit(tmp_path, commit):
    """One command for PR CI and the deploy; an unknown stamp is the script's to handle."""
    root = tmp_path / 'ref'
    write_reference_file(root, URL, commit)
    reference = (root / '.agents' / 'TEMPLATE_REF.md').read_text(encoding='utf-8')
    code, out, calls = _run_step(tmp_path, reference)
    assert code == 0, out
    assert calls == [COMMAND], calls


@pytest.mark.skipif(shutil.which('bash') is None, reason='needs bash')
def test_the_template_itself_compares_nothing(tmp_path):
    code, out, calls = _run_step(tmp_path, reference=None)
    assert code == 0 and calls == [], out
    assert 'this is the template itself' in out


def test_dependabot_pull_requests_skip_only_the_drift_step():
    assert _step(STEP_NAME).get('if') == NOT_DEPENDABOT
    for name in ('Build the site', 'Check the built site against the docs-site standard'):
        assert 'if' not in _step(name), f"Dependabot PRs must still run {name!r}"


def test_a_pull_request_never_uploads_or_deploys():
    assert _step('Upload the Pages artifact').get('if') == NOT_A_PR
    assert _workflow()['jobs']['deploy'].get('if') == NOT_A_PR


def test_the_opt_in_block_arms_pull_request_with_the_push_paths(tmp_path):
    """--docs-site uncomments both triggers, over the same paths."""
    from bootstrap_template import enable_docs_site
    (tmp_path / '.github' / 'workflows').mkdir(parents=True)
    shutil.copyfile(DOCS_WORKFLOW, tmp_path / '.github' / 'workflows' / 'docs.yml')
    shutil.copyfile(ROOT_DIR / 'mkdocs.yml', tmp_path / 'mkdocs.yml')
    enable_docs_site(tmp_path, project_name='demo', repo_owner='acme')
    armed = yaml.safe_load((tmp_path / '.github' / 'workflows' / 'docs.yml')
                           .read_text(encoding='utf-8'))
    triggers = armed.get('on') or armed.get(True)
    assert set(triggers) == {'push', 'pull_request', 'workflow_dispatch'}, triggers
    assert triggers['pull_request']['paths'] == triggers['push']['paths']
    assert 'requirements-docs.txt' in triggers['pull_request']['paths'], (
        "a Dependabot bump of the docs dependencies must trigger PR CI")


def test_dependabot_ignores_mkdocs_2():
    pip = next(update for update in yaml.safe_load(DEPENDABOT.read_text(encoding='utf-8'))
               ['updates'] if update['package-ecosystem'] == 'pip')
    assert {'dependency-name': 'mkdocs', 'versions': ['>= 2']} in pip.get('ignore', [])
