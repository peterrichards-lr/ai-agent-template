---
name: tool-use-react
description: >-
  Enforces ReAct reasoning patterns, non-interactive CLI defaults (-y), and tool safety boundaries.
  Load when invoking terminal tools, file modifications, or background tasks.
---

# Skill: Tool Use & ReAct Reasoning

---

## Directives & Rules of Engagement

### 1. ReAct Pattern (Reasoning Before Acting)

Before calling any tool, the agent MUST explicitly articulate its reasoning:

- **Observation / Intent**: What file or state is being inspected or modified.
- **Tool Selection**: Why the specific tool is appropriate.
- **Expected Outcome**: What success looks like.

### 2. Non-Interactive CLI Boundaries

All CLI commands executed via the agent's terminal/command-execution tool MUST append non-interactive options:

- `npm`: `--yes` or `-y`
- `apt-get`: `-y`
- `docker`: `--detach` or non-interactive flags
- `git`: non-interactive environment settings

**This does not override `human-in-the-loop/SKILL.md`.** These flags exist to
stop a tool getting *stuck* waiting on a routine, safe confirmation (a normal
init/install prompt) -- they must never be used to auto-confirm a prompt that
exists specifically to stop a destructive or irreversible action (deleting
data, dropping/truncating a database, an unreviewed package install with
side effects, a production deployment, etc.). If a confirmation prompt could
plausibly be either, treat it as the latter and stop for human approval
instead of suppressing it.

### 3. Asynchronous Task Lifecycle

After launching long-running or asynchronous background commands, the agent MUST NOT poll in a loop. Either proceed to independent parallel work or provide a brief status update and end the turn. The system will automatically wake the agent upon completion.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-04* | *Last Reviewed: 2026-09-04*
