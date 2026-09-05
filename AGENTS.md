# AI Agent Template - Canonical Agent Context

This document is the single source of truth for AI agent rules in this repository across all AI providers (Gemini, Claude, Cursor, Copilot, etc.). It acts as a canonical router pointing to modular skill instructions under `.agents/skills/` and in-flight scratchpad state in `.agent-state.md`.

Provider discovery files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`) exist only so each tool finds this file, and redirect straight back here. Do not duplicate context into them.

---

## 1. Project Identity & Architecture

- **Repository**: `ai-agent-template` - reusable multi-language project template for AI Agent-assisted development.
- **Provider-Agnostic Model**: Discovery files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`) redirect to `AGENTS.md`. In-flight task scratchpad lives in `.agent-state.md` (gitignored).
- **Native Claude Code Discovery**: `.claude/skills` is a tracked relative symlink to `../.agents/skills`, allowing Claude Code to discover all skills natively without duplication.
  > [!NOTE]
  > **Windows Checkouts (`core.symlinks`)**: On Windows, Git defaults to checking out symlinks as plain text files unless Developer Mode is enabled or Git is configured with `core.symlinks=true` (`git clone -c core.symlinks=true <repo>` or `git config core.symlinks true`). If checked out as text, Claude Code will fail to traverse `.claude/skills/`.
- **Quality Gates**: Pre-commit hooks, documentation timestamp footers, linting, and automated unit testing per language ecosystem stack.

---

## 2. Skills Routing Directory

Project rules are organized into active, modular skill files located under `.agents/skills/`. Reference and activate the corresponding skill file when executing relevant tasks:

| Skill Name | Skill Path | Trigger Condition / When to Load | Description |
| :--- | :--- | :--- | :--- |
| **[reflection-and-planning](file:///.agents/skills/reflection-and-planning/SKILL.md)** | [.agents/skills/reflection-and-planning/SKILL.md](file:///.agents/skills/reflection-and-planning/SKILL.md) | Beginning complex tasks, multi-file edits, or architectural changes. | Enforces logic-first planning, implementation plans, failure analysis, and approval loops. |
| **[human-in-the-loop](file:///.agents/skills/human-in-the-loop/SKILL.md)** | [.agents/skills/human-in-the-loop/SKILL.md](file:///.agents/skills/human-in-the-loop/SKILL.md) | Deployments, database drops, secrets generation, or opening PRs. | Enforces strict human verification gates before high-risk or irreversible operations. |
| **[coding-standards](file:///.agents/skills/coding-standards/SKILL.md)** | [.agents/skills/coding-standards/SKILL.md](file:///.agents/skills/coding-standards/SKILL.md) | Writing, refactoring, or reviewing source code logic across any language. | Enforces DRY code, self-documenting style, predictive failure analysis, and safety guards. |
| **[unit-testing](file:///.agents/skills/unit-testing/SKILL.md)** | [.agents/skills/unit-testing/SKILL.md](file:///.agents/skills/unit-testing/SKILL.md) | Writing tests, running verification, or investigating test failures. | Governs test-driven development, coverage checking, and non-interactive command execution. |
| **[documentation](file:///.agents/skills/documentation/SKILL.md)** | [.agents/skills/documentation/SKILL.md](file:///.agents/skills/documentation/SKILL.md) | After implementing any feature, code change, or bug fix. | Details active documentation review, timestamp hygiene, and staleness checks. |
| **[github-workflow](file:///.agents/skills/github-workflow/SKILL.md)** | [.agents/skills/github-workflow/SKILL.md](file:///.agents/skills/github-workflow/SKILL.md) | Managing issues, creating PRs, repository SEO, or resolving CI pipeline failures. | Governs GitHub CLI usage, issue linking (`Closes #<issue>`), repository SEO (description & topics), and CI run cleanup. |
| **[tool-use-react](file:///.agents/skills/tool-use-react/SKILL.md)** | [.agents/skills/tool-use-react/SKILL.md](file:///.agents/skills/tool-use-react/SKILL.md) | Executing terminal commands, file tools, or background tasks. | Enforces ReAct reasoning patterns, non-interactive flags (`-y`), and tool safety boundaries. |
| **[multi-agent-orchestration](file:///.agents/skills/multi-agent-orchestration/SKILL.md)** | [.agents/skills/multi-agent-orchestration/SKILL.md](file:///.agents/skills/multi-agent-orchestration/SKILL.md) | Delegating tasks to subagents or running parallel background research. | Defines subagent invocation, prompt framing, and async result synthesis. |
| **[rule-adherence](file:///.agents/skills/rule-adherence/SKILL.md)** | [.agents/skills/rule-adherence/SKILL.md](file:///.agents/skills/rule-adherence/SKILL.md) | Before merging, deploying, tagging a release, applying a ruleset, or declaring a task complete. | Addresses agents not reliably following prose rules: re-read before acting, prefer checkable artifacts, and self-correct visibly. |
| **[release-management](file:///.agents/skills/release-management/SKILL.md)** | [.agents/skills/release-management/SKILL.md](file:///.agents/skills/release-management/SKILL.md) | Tagging a version, publishing a release, or when merged changes accumulate. | Governs semantic versioning, release notes, auditing issue closure, and human verification gates. |

---

## 3. Current Work State

Active, in-flight task state and intra-task scratchpad context are maintained locally in `.agent-state.md` (gitignored). `scripts/bootstrap_template.py` seeds it from the tracked template [`.agents/templates/agent-state.md`](./.agents/templates/agent-state.md); if it is missing, recreate it by copying that seed.

- **On Session Startup**: If `.agent-state.md` exists, read it to discover active objectives and resume in-flight work without lost context across AI provider switches.
- **During Execution**: Update `.agent-state.md` when making progress, encountering blockers, or pausing a workflow.
- **On Feature Completion**: Clear or reset `.agent-state.md` once all objectives and verification steps are met.

---

## 4. Universal Rules of Engagement

### 1. Anti-Hallucination Protocol
Any technical statement, architecture decision, or bug diagnosis MUST be verified against actual code using search and file viewing tools before taking action. Do not guess variable names, file paths, or API signatures.

### 2. Active Documentation Maintenance Rule
After completing any feature or code change, the agent MUST inspect the project documentation, execute `scripts/append_timestamps.py` to update timestamp footers, and run `scripts/check_docs_review.py` to ensure document policy compliance.

### 3. Non-Interactive Default
Whenever executing CLI commands or developer tools via terminal, the agent MUST explicitly append non-interactive flags (e.g. `-y`, `--non-interactive`, `--batch`, `-n`) to prevent blocking interactive prompts -- for routine, safe confirmations only. This never overrides `human-in-the-loop/SKILL.md`'s Rule 1 (High-Risk Operation Gates).

### 4. Technical Debt Logging
If the agent encounters technical debt during a task (Code Smells, Duplication, Missing Tests, Security Hygiene, Config Drift, Doc Debt, etc.), it must track it as a GitHub issue labeled `tech-debt` -- see `github-workflow/SKILL.md` rule 4 for the full policy.

### 5. Primary Unit Testing Command
Primary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`

### 6. Rule Adherence
Before a high-commitment action (merging, deploying, tagging, applying a ruleset), re-read the specific governing skill file fresh rather than relying on memory. See `rule-adherence/SKILL.md` for full guidance.

---

## 5. Related References

| File | Purpose |
| :--- | :--- |
| [`.agent-state.md`](./.agent-state.md) | In-flight task state, synced between AI providers. Gitignored. |
| [`.agents/templates/agent-state.md`](./.agents/templates/agent-state.md) | Tracked seed copied to `.agent-state.md` by `scripts/bootstrap_template.py`. |
| [`README.md`](./README.md) | Consumer-facing documentation & quick setup. |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Contribution guidelines and quality gate commands. |
| [`.claude/skills`](./.claude/skills) | Tracked symlink to [`.agents/skills/`](./.agents/skills) for Claude Code auto-discovery. |
| [`CLAUDE.md`](./CLAUDE.md) | Claude CLI discovery redirect. |
| [`GEMINI.md`](./GEMINI.md) | Gemini CLI discovery redirect. |
| [`.cursorrules`](./.cursorrules) | Cursor IDE discovery redirect. |
| [`.windsurfrules`](./.windsurfrules) | Windsurf IDE discovery redirect. |
| [`.github/copilot-instructions.md`](./.github/copilot-instructions.md) | GitHub Copilot discovery redirect. |

<!-- markdownlint-disable MD049 -->

---

*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
