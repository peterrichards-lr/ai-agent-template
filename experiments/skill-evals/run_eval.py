#!/usr/bin/env python3
"""
run_eval.py - Measure whether the agent instructions in this repository earn their context.

Runs each task in tasks.json through a headless agent CLI, several times, in two or more
"arms" that differ only in the agent guidance present, and records for every run whether
the task's own check passed, how long it took, and -- when the agent reports it -- turns
and tokens. The summary compares arms per task.

Arms:
  full          the repository at HEAD, unchanged.
  no-guidance   AGENTS.md, every provider redirect, .agents/skills/ and .claude/skills
                removed: what the agent does with no instructions at all.
  without:<skill>  one skill removed and the AGENTS.md index regenerated: what that skill
                adds, i.e. whether it is worth its place in the eagerly loaded index.

Every run happens in a throwaway `git worktree` of HEAD, so uncommitted changes are not
evaluated and the checkout you run from is never modified.

Usage (from the repository root):
  python3 experiments/skill-evals/run_eval.py --trials 3
  python3 experiments/skill-evals/run_eval.py --arms full without:tool-use-react --tasks add-skill
  python3 experiments/skill-evals/run_eval.py --agent-cmd 'my-agent --prompt {prompt}'

The agent command is split with shlex; the token {prompt} is replaced by the task prompt
as one argument. Token and turn counts are parsed from the agent's stdout when it is a
JSON object (as `claude -p ... --output-format json` prints); anything not reported is
recorded as null -- unknown, never zero.
"""

import argparse
import json
import os
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DEFAULT_TASKS = HERE / 'tasks.json'
DEFAULT_RESULTS_DIR = HERE / 'results'
DEFAULT_AGENT_CMD = 'claude -p {prompt} --output-format json --permission-mode acceptEdits'
PROMPT_TOKEN = '{prompt}'
PYTHON_TOKEN = '{python}'

GUIDANCE_PATHS = (
    'AGENTS.md', 'CLAUDE.md', 'GEMINI.md', '.cursorrules', '.windsurfrules',
    '.github/copilot-instructions.md', '.agents/skills', '.claude/skills',
)
USAGE_FIELDS = ('input_tokens', 'output_tokens', 'cache_read_input_tokens',
                'cache_creation_input_tokens')


class EvalError(Exception):
    """Configuration that would make the measurement meaningless."""


def load_tasks(path: Path, selected=None) -> list:
    tasks = json.loads(path.read_text(encoding='utf-8')).get('tasks')
    if not isinstance(tasks, list) or not tasks:
        raise EvalError(f"{path}: expected a non-empty 'tasks' list")
    ids = set()
    for task in tasks:
        missing = [k for k in ('id', 'prompt', 'check') if not task.get(k)]
        if missing:
            raise EvalError(f"{path}: task {task.get('id', '?')!r} is missing {', '.join(missing)}")
        if task['id'] in ids:
            raise EvalError(f"{path}: duplicate task id {task['id']!r}")
        ids.add(task['id'])
    if selected:
        unknown = sorted(set(selected) - ids)
        if unknown:
            raise EvalError(f"unknown task id(s): {', '.join(unknown)}")
        tasks = [t for t in tasks if t['id'] in selected]
    return tasks


def remove_path(path: Path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def prepare_arm(worktree: Path, arm: str):
    """Shape the worktree's agent guidance for one arm, then commit it.

    Committing means the task's check (and the agent) sees a clean tree whose only
    difference between arms is the guidance.
    """
    if arm == 'full':
        return
    if arm == 'no-guidance':
        for rel in GUIDANCE_PATHS:
            remove_path(worktree / rel)
    elif arm.startswith('without:'):
        skill = arm.split(':', 1)[1]
        skill_dir = worktree / '.agents' / 'skills' / skill
        if not skill_dir.is_dir():
            raise EvalError(f"arm {arm!r}: no skill directory .agents/skills/{skill}")
        shutil.rmtree(skill_dir)
        subprocess.run([sys.executable, 'scripts/generate_skill_index.py'], cwd=worktree,
                       check=True, capture_output=True)
    else:
        raise EvalError(f"unknown arm {arm!r}; use full, no-guidance or without:<skill>")
    git(worktree, 'add', '-A')
    # Hooks are pointed at nothing for this one throwaway commit: it records the arm's
    # starting state in a worktree that is deleted afterwards, and is never pushed.
    git(worktree, '-c', 'user.email=eval@example.invalid', '-c', 'user.name=eval',
        '-c', f'core.hooksPath={os.devnull}', 'commit', '-q', '--no-gpg-sign',
        '-m', f'eval arm: {arm}')


def git(cwd: Path, *args):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True)


def shell(command: str, cwd: Path, timeout: int):
    command = command.replace(PYTHON_TOKEN, shlex.quote(sys.executable))
    return subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, check=False)


def parse_agent_report(stdout: str) -> dict:
    """Pull turns and tokens from a JSON report; None for anything not reported."""
    report = {'num_turns': None, 'cost_usd': None, **{f: None for f in USAGE_FIELDS}}
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return report
    if not isinstance(data, dict):
        return report
    if isinstance(data.get('num_turns'), int):
        report['num_turns'] = data['num_turns']
    if isinstance(data.get('total_cost_usd'), (int, float)):
        report['cost_usd'] = data['total_cost_usd']
    usage = data.get('usage') if isinstance(data.get('usage'), dict) else {}
    for field in USAGE_FIELDS:
        if isinstance(usage.get(field), int):
            report[field] = usage[field]
    return report


def run_one(task: dict, arm: str, trial: int, agent_cmd: str, timeout: int) -> dict:
    record = {'task': task['id'], 'arm': arm, 'trial': trial,
              'commit': git(REPO_ROOT, 'rev-parse', 'HEAD').stdout.strip()}
    with tempfile.TemporaryDirectory(prefix='skill-eval-') as tmp:
        worktree = Path(tmp) / 'wt'
        git(REPO_ROOT, 'worktree', 'add', '-q', '--detach', str(worktree), 'HEAD')
        try:
            prepare_arm(worktree, arm)
            if task.get('setup'):
                setup = shell(task['setup'], worktree, timeout)
                if setup.returncode != 0:
                    raise EvalError(f"task {task['id']!r}: setup failed: {setup.stderr.strip()}")

            argv = [task['prompt'] if part == PROMPT_TOKEN else part
                    for part in shlex.split(agent_cmd)]
            started = time.monotonic()
            try:
                agent = subprocess.run(argv, cwd=worktree, capture_output=True, text=True,
                                       timeout=timeout, check=False)
                record['agent_exit'], stdout = agent.returncode, agent.stdout
            except subprocess.TimeoutExpired:
                record['agent_exit'], stdout = 'timeout', ''
            record['duration_s'] = round(time.monotonic() - started, 1)
            record.update(parse_agent_report(stdout))

            check = shell(task['check'], worktree, timeout)
            record['check_exit'] = check.returncode
            record['success'] = check.returncode == 0
        finally:
            subprocess.run(['git', 'worktree', 'remove', '--force', str(worktree)],
                           cwd=REPO_ROOT, capture_output=True, check=False)
    return record


def summarise(records: list) -> str:
    """Markdown table: per task and arm, success rate and medians over reported values."""
    def median(values):
        known = [v for v in values if v is not None]
        return f"{statistics.median(known):g}" if known else 'n/a'

    rows = ['| Task | Arm | Success | Median s | Median turns | Median tokens in+out |',
            '| :--- | :--- | ---: | ---: | ---: | ---: |']
    keys = sorted({(r['task'], r['arm']) for r in records})
    for task, arm in keys:
        runs = [r for r in records if r['task'] == task and r['arm'] == arm]
        passed = sum(1 for r in runs if r['success'])
        tokens = [r['input_tokens'] + r['output_tokens']
                  if r['input_tokens'] is not None and r['output_tokens'] is not None else None
                  for r in runs]
        rows.append(f"| {task} | {arm} | {passed}/{len(runs)} | "
                    f"{median([r['duration_s'] for r in runs])} | "
                    f"{median([r['num_turns'] for r in runs])} | {median(tokens)} |")
    return '\n'.join(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--tasks-file', type=Path, default=DEFAULT_TASKS)
    parser.add_argument('--tasks', nargs='+', help='task ids to run (default: all)')
    parser.add_argument('--arms', nargs='+', default=['full', 'no-guidance'])
    parser.add_argument('--trials', type=int, default=3,
                        help='runs per task and arm; agents are noisy, so one run proves little')
    parser.add_argument('--agent-cmd', default=DEFAULT_AGENT_CMD)
    parser.add_argument('--timeout', type=int, default=1200, help='seconds per agent run')
    parser.add_argument('--results-dir', type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args(argv)

    if PROMPT_TOKEN not in shlex.split(args.agent_cmd):
        print(f"❌ --agent-cmd must contain {PROMPT_TOKEN} as its own argument", file=sys.stderr)
        return 2
    try:
        tasks = load_tasks(args.tasks_file, args.tasks)
        args.results_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        out_path = args.results_dir / f'{stamp}.jsonl'
        records = []
        with out_path.open('w', encoding='utf-8') as out:
            for task in tasks:
                for arm in args.arms:
                    for trial in range(1, args.trials + 1):
                        print(f"▶ {task['id']} / {arm} / trial {trial}", flush=True)
                        record = run_one(task, arm, trial, args.agent_cmd, args.timeout)
                        records.append(record)
                        out.write(json.dumps(record) + '\n')
                        out.flush()
    except EvalError as error:
        print(f"❌ {error}", file=sys.stderr)
        return 2

    print(f"\nRaw results: {out_path}\n")
    print(summarise(records))
    return 0


if __name__ == '__main__':
    sys.exit(main())
