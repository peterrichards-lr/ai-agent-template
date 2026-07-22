# Skill: Tool Use & ReAct Reasoning

**Trigger Condition**: Load this skill when invoking terminal tools (`run_command`), file editing tools, or background tasks.

---

## Directives & Rules of Engagement

### 1. ReAct Pattern (Reasoning Before Acting)

Before calling any tool, the agent MUST explicitly articulate its reasoning:

- **Observation / Intent**: What file or state is being inspected or modified.
- **Tool Selection**: Why the specific tool is appropriate.
- **Expected Outcome**: What success looks like.

### 2. Non-Interactive CLI Boundaries

All CLI commands executed via `run_command` MUST append non-interactive options:

- `npm`: `--yes` or `-y`
- `apt-get`: `-y`
- `docker`: `--detach` or non-interactive flags
- `git`: non-interactive environment settings

### 3. Asynchronous Task Lifecycle

After launching long-running or asynchronous background commands, the agent MUST NOT poll in a loop. Either proceed to independent parallel work or provide a brief status update and end the turn. The system will automatically wake the agent upon completion.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
