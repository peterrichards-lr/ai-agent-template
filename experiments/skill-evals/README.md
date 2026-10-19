# Skill Evaluations

The skills and rules in this repository are loaded into every agent session, so each one
costs context on every task. This harness measures whether they earn it: it runs the same
tasks through a headless agent with and without the guidance, several times each, and
compares success rate, time, turns and tokens.

It is an experiment, not a quality gate. Nothing here runs in CI or in `make verify`, and
results are written to the git-ignored `results/` directory.

## Run it

From the repository root, with a headless agent CLI on your `PATH`:

```bash
# Every task, full guidance versus none, three trials each
python3 experiments/skill-evals/run_eval.py --trials 3

# What does one skill add? Remove it and regenerate the AGENTS.md index.
python3 experiments/skill-evals/run_eval.py --arms full without:tool-use-react

# Another agent: {prompt} is replaced by the task prompt as a single argument
python3 experiments/skill-evals/run_eval.py --agent-cmd 'my-agent run --prompt {prompt}'
```

The default agent command is `claude -p {prompt} --output-format json --permission-mode
acceptEdits`. Tasks that need shell commands (running tests, regenerating the index) also need
those tools allowed for unattended runs; add `--allowedTools` rules to the command to suit. Do
not add `--bare`: it skips `CLAUDE.md` discovery, which would make every arm a no-guidance arm.

Each run happens in a throwaway `git worktree` of `HEAD`, so commit what you want measured.
Your checkout is never modified.

## Arms

| Arm | What the agent gets |
| :--- | :--- |
| `full` | The repository at `HEAD`, unchanged. |
| `no-guidance` | No `AGENTS.md`, no provider redirects, no `.agents/skills/`, no `.claude/skills`. |
| `without:<skill>` | Everything except one skill, with the `AGENTS.md` index regenerated. |

## Tasks

`tasks.json` holds the task corpus. Each task has a `prompt`, an optional `setup` command that
plants the problem, and a `check` command whose exit code decides success. `{python}` in either
command is replaced by the interpreter running the harness. Write checks that can pass in every
arm -- a check that needs `AGENTS.md` to exist would fail `no-guidance` for the wrong reason.

The seed tasks each exercise something the guidance teaches: fixing a planted bug without
breaking the tests, adding a skill so that the generated index stays current, and updating
documentation including its *Last Updated* footer. Add tasks that reflect the work your
agents actually do; three tasks are a starting point, not a benchmark.

## Reading the results

Agents are noisy. One run per arm proves nothing, and a difference of one success in three
trials is not a finding. Turns and tokens are recorded only when the agent reports them (as
`claude --output-format json` does) and are shown as `n/a` otherwise -- never as zero. A
skill whose removal changes neither success nor cost on tasks it should matter for is a
candidate for cutting or rewriting.

The template's own test suite exercises the harness with stand-in agents; those tests prove
the plumbing, not any model's behaviour.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-10-12* | *Last Reviewed: 2026-10-12*
