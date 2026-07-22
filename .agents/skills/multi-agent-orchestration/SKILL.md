# Skill: Multi-Agent Orchestration & Delegation

**Trigger Condition**: Load this skill when delegating subtasks to subagents (`invoke_subagent`), spawning research subagents, or coordinating multi-agent workflows.

---

## Directives & Rules of Engagement

### 1. Delegation Criteria
Delegate tasks to subagents when:
- Deep research or codebase surveying is required without cluttering the primary agent context window.
- Independent parallel tasks (e.g. running static analysis while researching documentation) can be performed.
- Isolated trial implementations or experimental refactoring should be tested safely.

### 2. Clear Context & Prompt Framing
Subagent prompts MUST be explicit and self-contained:
- State the specific goal and target files clearly.
- Specify what output format is expected (e.g. summary table, diff, JSON report).
- Provide necessary background context or links to relevant project documentation.

### 3. Asynchronous Synthesis
Do not poll subagents in a loop. When subagents finish, synthesize their returned insights into a clean, natural language summary with clear next actions.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
