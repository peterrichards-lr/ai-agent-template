# Master AI Agent Rules & Skills Directory

To prevent agent prompt bloat, cognitive overload, and excessive token usage, project rules are organized into active, modular skill files located under `.agents/skills/`.

This document acts as the central **Routing Index**. When performing specific software engineering tasks, the AI agent must reference and activate the corresponding skill file.

---

## Skills Directory & Activation Routing

| Skill Name | Skill Path | Trigger Condition / When to Load | Description |
| :--- | :--- | :--- | :--- |
| **[reflection-and-planning](file:///.agents/skills/reflection-and-planning/SKILL.md)** | [.agents/skills/reflection-and-planning/SKILL.md](file:///.agents/skills/reflection-and-planning/SKILL.md) | Beginning complex tasks, multi-file edits, or architectural changes. | Enforces logic-first planning, implementation plans, failure analysis, and approval loops. |
| **[human-in-the-loop](file:///.agents/skills/human-in-the-loop/SKILL.md)** | [.agents/skills/human-in-the-loop/SKILL.md](file:///.agents/skills/human-in-the-loop/SKILL.md) | Deployments, database drops, secrets generation, or opening PRs. | Enforces strict human verification gates before high-risk or irreversible operations. |
| **[coding-standards](file:///.agents/skills/coding-standards/SKILL.md)** | [.agents/skills/coding-standards/SKILL.md](file:///.agents/skills/coding-standards/SKILL.md) | Writing, refactoring, or reviewing source code logic across any language. | Enforces DRY code, self-documenting style, predictive failure analysis, and safety guards. |
| **[unit-testing](file:///.agents/skills/unit-testing/SKILL.md)** | [.agents/skills/unit-testing/SKILL.md](file:///.agents/skills/unit-testing/SKILL.md) | Writing tests, running verification, or investigating test failures. | Governs test-driven development, coverage checking, and non-interactive command execution. |
| **[documentation](file:///.agents/skills/documentation/SKILL.md)** | [.agents/skills/documentation/SKILL.md](file:///.agents/skills/documentation/SKILL.md) | After implementing any feature, code change, or bug fix. | Details active documentation review, timestamp hygiene, and staleness checks. |
| **[github-workflow](file:///.agents/skills/github-workflow/SKILL.md)** | [.agents/skills/github-workflow/SKILL.md](file:///.agents/skills/github-workflow/SKILL.md) | Managing issues, creating PRs, or resolving CI pipeline failures. | Governs GitHub CLI usage, issue linking (`Closes #<issue>`), PR constraints, and CI run cleanup. |
| **[tool-use-react](file:///.agents/skills/tool-use-react/SKILL.md)** | [.agents/skills/tool-use-react/SKILL.md](file:///.agents/skills/tool-use-react/SKILL.md) | Executing terminal commands, file tools, or background tasks. | Enforces ReAct reasoning patterns, non-interactive flags (`-y`), and tool safety boundaries. |
| **[multi-agent-orchestration](file:///.agents/skills/multi-agent-orchestration/SKILL.md)** | [.agents/skills/multi-agent-orchestration/SKILL.md](file:///.agents/skills/multi-agent-orchestration/SKILL.md) | Delegating tasks to subagents or running parallel background research. | Defines subagent invocation, prompt framing, and async result synthesis. |

---

## Universal Rules of Engagement

### 1. No Assumptions (Anti-Hallucination Protocol)
Any technical statement, architecture decision, or bug diagnosis MUST be verified against actual code using search and file viewing tools before taking action. Do not guess variable names, file paths, or API signatures.

### 2. Active Documentation Maintenance Rule
After completing any feature or code change, the agent MUST inspect the project documentation, execute `scripts/append_timestamps.py` to update timestamp footers, and run `scripts/check_docs_review.py` to ensure document policy compliance.

### 3. Non-Interactive Default
Whenever executing CLI commands or developer tools via terminal, the agent MUST explicitly append non-interactive flags (e.g. `-y`, `--non-interactive`, `--batch`, `-n`) to prevent blocking interactive prompts.

### 4. Technical Debt Logging
If the agent encounters technical debt during a task (Code Smells, Duplication, Missing Tests, Security Hygiene, Config Drift, Doc Debt), it must immediately log a GitHub issue using `gh issue create --label "tech-debt"`.

### 5. Primary Unit Testing Command
Primary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
