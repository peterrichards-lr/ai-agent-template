"""
test_skill_evals.py - Tests for experiments/skill-evals/run_eval.py.

The harness itself is exercised end to end with a stand-in agent (a Python one-liner),
so these tests prove the plumbing -- worktree isolation, arm preparation, the task check,
report parsing and the summary -- without calling a real model.
"""

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / 'experiments' / 'skill-evals'))

import run_eval  # noqa: E402

FAKE_REPORT = {'num_turns': 3, 'total_cost_usd': 0.01,
               'usage': {'input_tokens': 100, 'output_tokens': 20}}


def fake_agent_cmd(script: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} {{prompt}}"


def write_tasks(tmp_path, tasks) -> Path:
    path = tmp_path / 'tasks.json'
    path.write_text(json.dumps({'tasks': tasks}), encoding='utf-8')
    return path


def test_shipped_tasks_file_is_valid():
    tasks = run_eval.load_tasks(run_eval.DEFAULT_TASKS)
    assert {t['id'] for t in tasks} >= {'fix-ignored-dirs', 'add-skill', 'document-base-ref'}


@pytest.mark.parametrize('tasks, message', [
    ([], "non-empty 'tasks'"),
    ([{'id': 'a', 'prompt': 'p'}], 'missing check'),
    ([{'id': 'a', 'prompt': 'p', 'check': 'true'}] * 2, 'duplicate task id'),
])
def test_invalid_tasks_are_rejected(tmp_path, tasks, message):
    with pytest.raises(run_eval.EvalError, match=message):
        run_eval.load_tasks(write_tasks(tmp_path, tasks))


def test_unknown_selected_task_is_rejected():
    with pytest.raises(run_eval.EvalError, match='unknown task'):
        run_eval.load_tasks(run_eval.DEFAULT_TASKS, ['no-such-task'])


def test_agent_report_parsing_keeps_unreported_values_unknown():
    assert run_eval.parse_agent_report('not json')['input_tokens'] is None
    report = run_eval.parse_agent_report(json.dumps(FAKE_REPORT))
    assert report['num_turns'] == 3 and report['input_tokens'] == 100
    assert report['cache_read_input_tokens'] is None


def test_end_to_end_run_records_success_and_isolates_the_checkout(tmp_path, capsys):
    before = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT_DIR,
                            capture_output=True, text=True, check=True).stdout
    script = (
        "import json, pathlib; "
        "pathlib.Path('answer.txt').write_text(str(pathlib.Path('AGENTS.md').exists())); "
        f"print(json.dumps({FAKE_REPORT!r}))"
    )
    tasks = write_tasks(tmp_path, [{'id': 'probe', 'prompt': 'write answer.txt',
                                    'check': 'test -f answer.txt'}])
    results = tmp_path / 'results'

    assert run_eval.main(['--tasks-file', str(tasks), '--arms', 'full', 'no-guidance',
                          'without:tool-use-react', '--trials', '1',
                          '--agent-cmd', fake_agent_cmd(script),
                          '--results-dir', str(results)]) == 0

    records = [json.loads(line) for line in next(results.glob('*.jsonl')).read_text().splitlines()]
    assert [r['arm'] for r in records] == ['full', 'no-guidance', 'without:tool-use-react']
    assert all(r['success'] and r['agent_exit'] == 0 and r['num_turns'] == 3 for r in records)
    assert '| probe | full | 1/1 |' in capsys.readouterr().out

    after = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT_DIR,
                           capture_output=True, text=True, check=True).stdout
    assert after == before, "the evaluated checkout must never be modified"
    assert not (ROOT_DIR / 'answer.txt').exists()


def test_arms_shape_the_guidance(tmp_path):
    worktree = tmp_path / 'wt'
    subprocess.run(['git', 'worktree', 'add', '-q', '--detach', str(worktree), 'HEAD'],
                   cwd=ROOT_DIR, check=True, capture_output=True)
    try:
        run_eval.prepare_arm(worktree, 'without:tool-use-react')
        assert not (worktree / '.agents' / 'skills' / 'tool-use-react').exists()
        assert 'tool-use-react' not in (worktree / 'AGENTS.md').read_text(encoding='utf-8').split(
            'BEGIN GENERATED')[1].split('END GENERATED')[0]

        run_eval.prepare_arm(worktree, 'no-guidance')
        for rel in run_eval.GUIDANCE_PATHS:
            assert not (worktree / rel).exists() and not (worktree / rel).is_symlink(), rel

        with pytest.raises(run_eval.EvalError, match='unknown arm'):
            run_eval.prepare_arm(worktree, 'bogus')
    finally:
        subprocess.run(['git', 'worktree', 'remove', '--force', str(worktree)],
                       cwd=ROOT_DIR, capture_output=True, check=False)


def test_agent_command_without_the_prompt_token_is_refused(capsys):
    assert run_eval.main(['--agent-cmd', 'claude -p hello', '--trials', '1']) == 2
    assert '{prompt}' in capsys.readouterr().err
