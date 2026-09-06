AGENTS_MD = """# AI Agent Template - Canonical Agent Context

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
| **[no-assumptions](file:///.agents/skills/no-assumptions/SKILL.md)** | [.agents/skills/no-assumptions/SKILL.md](file:///.agents/skills/no-assumptions/SKILL.md) | **Always** -- no trigger condition and no off state; re-read after any context compaction or session resume. | Forbids any technical claim not verified by a tool call made in the current session. |
| **[reflection-and-planning](file:///.agents/skills/reflection-and-planning/SKILL.md)** | [.agents/skills/reflection-and-planning/SKILL.md](file:///.agents/skills/reflection-and-planning/SKILL.md) | Beginning complex tasks, multi-file edits, or architectural changes. | Enforces logic-first planning, implementation plans, failure analysis, and approval loops. |
| **[human-in-the-loop](file:///.agents/skills/human-in-the-loop/SKILL.md)** | [.agents/skills/human-in-the-loop/SKILL.md](file:///.agents/skills/human-in-the-loop/SKILL.md) | Deployments, database drops, secrets generation, or opening PRs. | Enforces strict human verification gates before high-risk or irreversible operations. |
| **[coding-standards](file:///.agents/skills/coding-standards/SKILL.md)** | [.agents/skills/coding-standards/SKILL.md](file:///.agents/skills/coding-standards/SKILL.md) | Writing, refactoring, or reviewing source code logic across any language. | Enforces DRY code, self-documenting style, predictive failure analysis, and safety guards. |
| **[unit-testing](file:///.agents/skills/unit-testing/SKILL.md)** | [.agents/skills/unit-testing/SKILL.md](file:///.agents/skills/unit-testing/SKILL.md) | Writing tests, running verification, or investigating test failures. | Governs test-driven development, coverage checking, and non-interactive command execution. |
| **[e2e-verification](file:///.agents/skills/e2e-verification/SKILL.md)** | [.agents/skills/e2e-verification/SKILL.md](file:///.agents/skills/e2e-verification/SKILL.md) | Changes unit tests cannot prove: UI/rendering, process or network boundaries, CLI interaction, config/deployment. | Defines real-system e2e behavior and environment interaction. |
| **[context-compaction](file:///.agents/skills/context-compaction/SKILL.md)** | [.agents/skills/context-compaction/SKILL.md](file:///.agents/skills/context-compaction/SKILL.md) | When agent state exceeds token limits or context window. | Manages token economy, summarizing, and preserving state fidelity during long sessions. |
| **[session-resume](file:///.agents/skills/session-resume/SKILL.md)** | [.agents/skills/session-resume/SKILL.md](file:///.agents/skills/session-resume/SKILL.md) | Upon re-loading `.agent-state.md` after a potential context shift. | Bridges the gap between previous tasks and current understanding without re-scan. |
| **[documentation-footers](file:///.agents/skills/documentation-footers/SKILL.md)** | [.agents/skills/documentation-footers/SKILL.md](file:///.agents/skills/documentation-footers/SKILL.md) | Every time a document is committed, reviewed, or timestamped. | Ensures metadata stays fresh, adding author/date context to immutable markdown. |
| **[artifact-generation](file:///.agents/skills/artifact-generation/SKILL.md)** | [.agents/skills/artifact-generation/SKILL.md](file:///.agents/skills/artifact-generation/SKILL.md) | When outputting new files, configs, or CLI artifacts to the repo root. | Standardizes how new files appear in the tree, maintaining consistent structure. |
| **[prompt-engineering](file:///.agents/skills/prompt-engineering/SKILL.md)** | [.agents/skills/prompt-engineering/SKILL.md](file:///.agents/skills/prompt-engineering/SKILL.md) | Constructing or refining the system prompts that drive the agents. | Optimizes the LLM inputs, ensuring tokens are spent wisely on instruction. |
| **[state-management](file:///.agents/skills/state-management/SKILL.md)** | [.agents/skills/state-management/SKILL.md](file:///.agents/skills/state-management/SKILL.md) | Tracking mutable data across tool calls and external integrations. | Decouples ephemeral tool output from persistent repository state in memory. |
| **[environment-scoping](file:///.agents/skills/environment-scoping/SKILL.md)** | [.agents/skills/environment-scoping/SKILL.md](file:///.agents/skills/environment-scoping/SKILL.md) | When tool outputs are ambiguous or path resolution varies by OS. | Resolves path normalization issues, ensuring `file://` URIs point correctly. |

---

## 3. Discovery & Metadata

This section points the "discovery" files to this single source of truth. They act as thin wrappers to satisfy Git LFS and Git Blame requirements without bloating the logic.

- **`.claude/skills`**: Tracked symlink to `.agents/skills`.
- **`GEMINI.md`**: The entry point for Gemini-based chains.
- **`.cursorrules`**: Directives for the Cursor IDE.

---

## 4. Maintenance & Versioning

- **Timestamp**: Managed by pre-commit hooks.
- **Schema**: Stable Markdown table format.
- **Git Strategy**: Tracked in `.gitattributes` with `diff=word` to prevent whitespace fights.

> [!TIP]
> **To update**: Modify the `.agents/skills/` files, then let the state manager regenerate this view if auto-magic is enabled.
"""