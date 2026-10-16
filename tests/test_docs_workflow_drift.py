"""
test_docs_workflow_drift.py - The shipped deploy picks its drift comparison from the stamp

`.github/workflows/docs.yml` is the deploy. A template merge must not block publishing, so it
runs `check_template_drift.py --against-recorded` when `.agents/TEMPLATE_REF.md` records a real
commit. A fresh project's stamp is `unknown`, and --against-recorded exits 3 on it, so until a
real commit is recorded it compares against upstream HEAD instead.

The step's own shell is run, not a restatement of it. A `python` shim on PATH records the drift
check's arguments rather than cloning anything; every other `python` call, including the one
that reads the stamp through the drift checker's own parser, runs for real.

A dedicated module, so parallel work on tests/test_template_drift.py does not conflict.
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
SEED = ROOT_DIR / '.agents' / 'templates' / 'template-ref.md'
STEP_NAME = 'Check the shared docs files against the template'
URL = 'https://github.com/peterrichards-lr/ai-agent-template'


def _drift_step():
    steps = yaml.safe_load(DOCS_WORKFLOW.read_text(encoding='utf-8'))['jobs']['build']['steps']
    return next(step['run'] for step in steps if step.get('name') == STEP_NAME)


def _run_step(tmp_path, reference=None):
    """Run the step in a fake checkout; return (exit code, output, drift-check argv lines)."""
    project = tmp_path / 'project'
    (project / 'scripts').mkdir(parents=True)
    shutil.copyfile(ROOT_DIR / 'scripts' / 'check_template_drift.py',
                    project / 'scripts' / 'check_template_drift.py')
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
    # GitHub runs a `run:` block with `bash -e`.
    result = subprocess.run(['bash', '-e', '-c', _drift_step()], cwd=project, env=env,
                            capture_output=True, text=True, check=False)
    calls = log.read_text(encoding='utf-8').splitlines() if log.exists() else []
    return result.returncode, result.stdout + result.stderr, calls


def _reference(tmp_path, commit):
    root = tmp_path / 'ref'
    write_reference_file(root, URL, commit)
    return (root / '.agents' / 'TEMPLATE_REF.md').read_text(encoding='utf-8')


pytestmark = pytest.mark.skipif(shutil.which('bash') is None, reason='needs bash')


def test_a_recorded_commit_compares_against_it(tmp_path):
    code, out, calls = _run_step(tmp_path, _reference(tmp_path, '25de5d1'))
    assert code == 0, out
    assert calls == ['scripts/check_template_drift.py --docs-site --fail-on-drift '
                     '--against-recorded'], calls
    assert 'recorded commit 25de5d1' in out


def test_an_unknown_stamp_compares_against_head(tmp_path):
    code, out, calls = _run_step(tmp_path, _reference(tmp_path, 'unknown'))
    assert code == 0, out
    assert calls == ['scripts/check_template_drift.py --docs-site --fail-on-drift'], calls


def test_a_fresh_projects_seeded_stamp_compares_against_head(tmp_path):
    """The seed bootstrap copies records `unknown`: a first deploy must not exit 3."""
    code, out, calls = _run_step(tmp_path, SEED.read_text(encoding='utf-8'))
    assert code == 0, out
    assert calls == ['scripts/check_template_drift.py --docs-site --fail-on-drift'], calls


def test_the_template_itself_compares_nothing(tmp_path):
    code, out, calls = _run_step(tmp_path, reference=None)
    assert code == 0 and calls == [], out
    assert 'this is the template itself' in out


def test_an_unparseable_reference_fails_the_step_rather_than_guessing(tmp_path):
    code, out, calls = _run_step(tmp_path, '# Template Reference\n\nno stamp here\n')
    assert code != 0 and calls == [], out
