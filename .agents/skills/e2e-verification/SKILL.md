---
name: e2e-verification
description: >-
  Defines end-to-end evidence for changes unit tests cannot prove. Load for UI, network, CLI, or deployment changes, and before escalating verification to a human.
---

# Skill: End-to-End & Real-App Verification

`unit-testing/SKILL.md` rule 3 forbids declaring a task resolved on file edits alone: the test
suite must be run and its clean output verified. This skill governs the other half of the same
question -- **what counts as proof for the class of changes where a green test suite proves
almost nothing**.

The two skills are complementary branches of one decision. `unit-testing/SKILL.md` rule 2
(Fail-First Verification Gate) tightens what a *passing test* proves; this skill covers changes
where a passing test was never the relevant evidence in the first place. Read both before
declaring a change verified.

---

## Directives & Rules of Engagement

### 1. Decision Rule: When Unit Tests Are Insufficient Evidence

Before citing the test suite as your stopping condition, ask whether the change is one of
these. If it is, a green suite is a precondition, not the proof:

- **UI, rendering, or layout** -- anything whose correctness is *visual*. A test can assert a
  class name was emitted; it cannot see that the element rendered, or rendered legibly.
- **Anything crossing a process or network boundary** -- a subprocess, a container, a socket,
  an HTTP or database client, an IPC channel. Unit tests mock the boundary, so they verify your
  code's behaviour against your *assumption* about the other side, not against the other side.
- **CLI interaction** -- argument parsing, prompts, exit codes, TTY behaviour, piping and
  redirection. The binary must actually be built and run.
- **Configuration and deployment** -- CI workflow files, container images, install scripts,
  environment wiring, permissions and settings files. These are only exercised when something
  loads them for real.
- **Any bug reported as "it behaves wrong when I..."** -- the report describes a *system*
  behaviour. The fix is verified when that system behaviour changes, not when a new unit test
  turns green.

### 2. What Counts as Evidence

Acceptable end-to-end evidence is an observation of the **running system**, captured and
citable:

| Change type | Acceptable evidence |
| :--- | :--- |
| UI / rendering | A screenshot of the rendered result, or a headless-browser assertion against the live DOM |
| HTTP / service integration | The actual HTTP response -- status line and body -- from a real request against a running instance |
| CLI behaviour | A captured session transcript: the exact command, its stdout/stderr, and its exit code |
| Subprocess / container / daemon | A log line from the running system showing the expected state, plus the process's exit status |
| Config / deployment | Output from the tool that consumed the config (a workflow run, a successful boot, a lint of the real file) |

> [!CAUTION]
> **A passing unit test that asserts the new code path is not evidence that the system works.**
> It is evidence that the new code path does what you wrote it to do. Those are different
> claims, and conflating them is the exact failure mode `unit-testing/SKILL.md` was written to
> prevent, one level up. Cite the observation, not the inference -- per `no-assumptions/SKILL.md`,
> the evidence must come from a tool call made in the current session.

Evidence must be **cited in the PR description**, in the same way fail-first red-to-green
evidence is, so a reviewer can check it without access to your local scratchpad.

### 3. Non-Interactive Execution and Mandatory Teardown

`tool-use-react/SKILL.md` applies in full: every command run to stand up or drive the system
MUST be non-interactive (`-y`, `--ci`, `--headless`, `--detach`, explicit `--no-input` flags),
and long-running processes MUST be started as background tasks with their output captured to a
file you then read -- never left to block the session.

Whatever you start, you MUST tear down:

- Stop and remove containers, servers, and background processes you launched, and verify they
  are gone (`docker ps`, `lsof -i`, checking the process is no longer running).
- Delete temporary databases, volumes, fixtures, build artefacts, and captured logs that were
  scratch, keeping only the evidence you cite.
- Never leave a port bound or a container running as a side effect of verification. If teardown
  fails, say so explicitly rather than leaving it for the human to discover.

### 4. Escalation When End-to-End Cannot Be Automated

Some verification genuinely cannot be automated here: no credentials for the target system, no
display, hardware in the loop, or a judgement that is inherently visual. In that case
`human-in-the-loop/SKILL.md` applies -- but escalation is only useful if it is *specific*.

**Forbidden**: "Please verify this works." That hands the entire problem back, including the
part you were able to determine.

**Required**: state, in the PR or the message requesting verification --

1. **What to do** -- the exact steps, commands, or URL, in order.
2. **What to look at** -- the specific element, output line, or value that carries the answer.
3. **What a pass looks like** -- the concrete observable outcome, stated precisely enough that
   the human can answer yes or no without interpreting your intent.
4. **What a failure looks like**, if it is not simply the negation, and what you already ruled
   out on your own.

> Example: "Run `make dev` and open `http://localhost:8080/settings`. The 'Danger Zone' panel
> should render below the form with a red border and its delete button disabled until the
> confirmation field is typed. A pass is: the button is greyed out on load and becomes clickable
> only after typing the project name. I verified the disable logic in unit tests but cannot
> confirm the rendered state without a browser."

### 5. Per-Ecosystem Harnesses (Examples, Not Mandates)

Where a project needs a repeatable harness, scaffold one appropriate to the stack rather than
adopting a tool by default:

- **Web UI**: Playwright or Cypress in headless mode, with screenshots retained as artefacts.
- **CLI**: build the binary and run a smoke script asserting exit codes and golden output.
- **HTTP service**: start the service, exercise real endpoints with `curl`, assert on status
  and payload.
- **Container / compose**: bring the stack up detached, poll the healthcheck, assert, tear down.

Back the harness with its own CI workflow so the evidence is regenerated on every change rather
than produced once by hand.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
