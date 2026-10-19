# <PROJECT_NAME_PLACEHOLDER> - Canonical Agent Context

This document is the single source of truth for AI agent rules in this repository across all AI providers (Gemini, Claude, Cursor, Copilot, etc.). It acts as a canonical router pointing to modular skill instructions under `.agents/skills/` and in-flight scratchpad state in `.agent-state.md`.

Provider discovery files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`) exist only so each tool finds this file, and redirect straight back here. Do not duplicate context into them.

---

## 1. Project Identity & Architecture

- **Repository**: `<PROJECT_NAME_PLACEHOLDER>`
- **Provider-Agnostic Model**: Discovery files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`) redirect to `AGENTS.md`. In-flight task scratchpad lives in `.agent-state.md` (gitignored).
- **Native Claude Code Discovery**: `.claude/skills` is a tracked relative symlink to `../.agents/skills`, allowing Claude Code to discover all skills natively without duplication.
  > [!NOTE]
  > **Windows Checkouts (`core.symlinks`)**: On Windows, Git defaults to checking out symlinks as plain text files unless Developer Mode is enabled or Git is configured with `core.symlinks=true` (`git clone -c core.symlinks=true <repo>` or `git config core.symlinks true`). If checked out as text, Claude Code will fail to traverse `.claude/skills/`.
- **Quality Gates**: Pre-commit hooks, documentation timestamp footers, linting, and automated unit testing per language ecosystem stack.

---

## 2. Skills Routing Directory

Project rules are organized into active, modular skill files located under `.agents/skills/`. Reference and activate the corresponding skill file when executing relevant tasks:

<!-- BEGIN GENERATED: skill-index (scripts/generate_skill_index.py) -->
| Skill | When to load and what it governs |
| :--- | :--- |
| **[coding-standards](.agents/skills/coding-standards/SKILL.md)** | Enforces DRY code discovery, self-documenting identifiers, predictive failure analysis, and safety guards. Load when writing, refactoring, or reviewing code in any programming language. |
| **[docs-site-standard](.agents/skills/docs-site-standard/SKILL.md)** | Governs the shared MkDocs Material site standard: home-page layout, top-level navigation, GitHub alerts, the shared files and the rendered-output checks. Load whenever the docs site, its theme, home page, nav or shared files are touched. |
| **[documentation](.agents/skills/documentation/SKILL.md)** | Governs documentation hygiene, timestamp maintenance (*Last Updated* \| *Last Reviewed*), and staleness checks. Load after completing any code change, feature implementation, refactoring, or doc update. |
| **[documentation-review](.agents/skills/documentation-review/SKILL.md)** | Governs auditing an existing documentation set: measuring before diagnosing, inspecting rendered output, checking documents against the code, and fixing routing before restructuring. Load when reviewing or restructuring docs as a body of work, or when told they are overwhelming, stale, or hard to navigate. |
| **[e2e-verification](.agents/skills/e2e-verification/SKILL.md)** | Defines end-to-end evidence for changes unit tests cannot prove. Load for UI, network, CLI, or deployment changes, and before escalating verification to a human. |
| **[github-workflow](.agents/skills/github-workflow/SKILL.md)** | Standardizes GitHub CLI usage, mandatory issue linking (Closes #<issue>), the PR review feedback loop, repository SEO, and CI run triage. Load when managing issues, opening PRs, responding to review comments, or handling CI failures. |
| **[human-in-the-loop](.agents/skills/human-in-the-loop/SKILL.md)** | Enforces strict human verification gates before high-risk or irreversible operations. Load before deployments, database drops, secrets generation, or opening PRs. |
| **[multi-agent-orchestration](.agents/skills/multi-agent-orchestration/SKILL.md)** | Defines criteria and patterns for delegating tasks to subagents and synthesizing results asynchronously. Load when delegating subtasks or running background research. |
| **[no-assumptions](.agents/skills/no-assumptions/SKILL.md)** | Always active. Forbids any technical claim not verified by a tool call made in the current session, including after compaction or resume. |
| **[reflection-and-planning](.agents/skills/reflection-and-planning/SKILL.md)** | Enforces logic-first planning, written implementation plans, predictive failure analysis, and approval loops. Load when beginning complex tasks, multi-file edits, or architectural changes. |
| **[release-management](.agents/skills/release-management/SKILL.md)** | Governs semantic versioning, release notes generation, issue closure auditing, and release verification gates. Load when tagging versions or publishing releases. |
| **[rule-adherence](.agents/skills/rule-adherence/SKILL.md)** | Enforces explicit self-verification against prose rules, checkable artifacts, and visible self-correction. Load before high-commitment actions like merging, deploying, or declaring tasks complete. |
| **[template-sync](.agents/skills/template-sync/SKILL.md)** | Governs the bidirectional contract with the upstream AI agent template: consult it before writing a new agent rule locally, and push lessons learned back upstream. Load before authoring or amending any agent rule, skill, or guardrail, and when running the drift check. |
| **[tool-use-react](.agents/skills/tool-use-react/SKILL.md)** | Enforces ReAct reasoning patterns, non-interactive CLI defaults (-y), and tool safety boundaries. Load when invoking terminal tools, file modifications, or background tasks. |
| **[unit-testing](.agents/skills/unit-testing/SKILL.md)** | Enforces test-driven development, empirical verification gates, non-interactive test runs, and test suite integrity. Load when writing tests, refactoring, or investigating test failures. |
<!-- END GENERATED: skill-index -->

This table is generated from each skill's `SKILL.md` frontmatter (`name`, `description`) by
`scripts/generate_skill_index.py`; edit the frontmatter, then run `make skill-index`. A
pre-commit hook fails when the table is stale.

---

## 3. Current Work State

Active, in-flight task state and intra-task scratchpad context are maintained locally in `.agent-state.md` (gitignored). `scripts/bootstrap_template.py` seeds it from the tracked template [`.agents/templates/agent-state.md`](./.agents/templates/agent-state.md); if it is missing, recreate it by copying that seed.

- **On Session Startup**: If `.agent-state.md` exists, read it to discover active objectives and resume in-flight work without lost context across AI provider switches.
- **During Execution**: Update `.agent-state.md` when making progress, encountering blockers, or pausing a workflow.
- **On Feature Completion**: Clear or reset `.agent-state.md` once all objectives and verification steps are met.

---

## 4. Universal Rules of Engagement

### 1. Anti-Hallucination Protocol
Always active, never waivable: every technical claim MUST be verified by a tool call made in the current session -- see `no-assumptions/SKILL.md` for the full protocol, including the compaction and session-resume corollary.

### 2. Active Documentation Maintenance Rule
After completing any feature or code change, the agent MUST inspect the project documentation, execute `scripts/append_timestamps.py` to update timestamp footers, and run `scripts/check_docs_review.py` to ensure document policy compliance.

### 3. Non-Interactive Default
Whenever executing CLI commands or developer tools via terminal, the agent MUST explicitly append non-interactive flags (e.g. `-y`, `--non-interactive`, `--batch`, `-n`) to prevent blocking interactive prompts -- for routine, safe confirmations only. This never overrides `human-in-the-loop/SKILL.md`'s Rule 1 (High-Risk Operation Gates).

### 4. Technical Debt Logging
If the agent encounters technical debt during a task (Code Smells, Duplication, Missing Tests, Security Hygiene, Config Drift, Doc Debt, etc.), it must track it in this repository's canonical tracker -- one per repo, GitHub Issues by default, as an issue labeled `tech-debt`. See `github-workflow/SKILL.md` rule 4 for the full policy, and rule 7 for repos that also run an external tracker (Jira, Azure Boards, Linear).

### 5. Primary Unit Testing Command
Primary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`

The task runner (`Makefile`) is the single entrypoint vocabulary, identical in every
language stack, so an agent never has to work out which ecosystem's commands apply:

| Target | Contract |
| :--- | :--- |
| `make setup` | Install dev dependencies and the pre-commit Git hooks. |
| `make lint` | `pre-commit run --all-files` plus this stack's linters. |
| `make test` | This stack's non-interactive test command. |
| `make docs` | `generate_skill_index.py`, `append_timestamps.py`, then `check_docs_review.py` (rule 2). |
| `make check` | Fast inner loop while iterating: pre-commit on files changed relative to `BASE_REF` (default `origin/main`), then `test`. Never a substitute for `verify`. |
| `make verify` | `lint` + `test` + `docs` -- **exactly** what `.github/workflows/ci.yml` runs, split across its two jobs. |
| `make push` | Guarded commit-and-push (`scripts/agent_push.py`): refuses no-op pushes and unstaged trees, never bypasses the hooks. |
| `make help` | Self-documenting target list; the default goal. |

The ecosystem's real command is stated once, in the `Makefile`'s language profile block,
which `scripts/bootstrap_template.py --lang <stack>` fills in. `make verify` is therefore
the answer to "did I break CI", and the two cannot drift because CI invokes these targets
rather than restating them. CI splits the chain across two jobs -- `lint-tooling` + `docs`
always run, `lint-lang` + `test` sit behind a paths filter -- so the union is `make verify`
with nothing dropped and nothing run twice.

### 6. Rule Adherence
Before a high-commitment action (merging, deploying, tagging, applying a ruleset), re-read the specific governing skill file fresh rather than relying on memory. See `rule-adherence/SKILL.md` for full guidance.

---

## 5. Engineering Principles

Project-level defaults for how changes are made, complementing the per-task skills. They
are deliberately few and general: edit them to fit this project, and keep the list short.

1. **Fix where the problem is produced.** Parse, validate and normalise a value once, at
   the boundary that owns it; downstream code uses the owner's result rather than
   re-interpreting the raw input. Repair the producer before adding a downstream workaround.
2. **Unknown is not absent.** When a value cannot be determined, keep it explicitly
   unknown. Never let it default to "none", "false", "empty" or "not applicable".
3. **Finish the change.** Remove the code, aliases, wrappers and tests a change supersedes
   in the same change. If related cleanup remains, say what it is and why it was left.
4. **A green test is not the proof.** A passing regression test shows the symptom is gone,
   not that the brittleness behind it is. Report what was verified and how, and name what
   was not -- including anything checked only against a mock or simulation.
5. **Earn every abstraction.** Introduce one only when it removes complexity you have
   actually observed, not complexity you anticipate.

---

## 6. Related References

| File | Purpose |
| :--- | :--- |
| [`.agent-state.md`](./.agent-state.md) | In-flight task state, synced between AI providers. Gitignored. |
| [`.agents/templates/agent-state.md`](./.agents/templates/agent-state.md) | Tracked seed copied to `.agent-state.md` by `scripts/bootstrap_template.py`. |
| [`README.md`](./README.md) | Consumer-facing documentation & quick setup. |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Contribution guidelines and quality gate commands. |
| [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) | Contributor Covenant v2.1 community standards. |
| [`CHANGELOG.md`](./CHANGELOG.md) | Keep a Changelog history; update under `[Unreleased]` when merging user-visible changes. |
| [`.editorconfig`](./.editorconfig) | Shared editor baseline (UTF-8, LF, final newline, trimmed trailing whitespace) matching the pre-commit hygiene hooks. |
| [`.claude/skills`](./.claude/skills) | Tracked symlink to [`.agents/skills/`](./.agents/skills) for Claude Code auto-discovery. |
| [`CLAUDE.md`](./CLAUDE.md) | Claude CLI discovery redirect. |
| [`GEMINI.md`](./GEMINI.md) | Gemini CLI discovery redirect. |
| [`.cursorrules`](./.cursorrules) | Cursor IDE discovery redirect. |
| [`.windsurfrules`](./.windsurfrules) | Windsurf IDE discovery redirect. |
| [`.github/copilot-instructions.md`](./.github/copilot-instructions.md) | GitHub Copilot discovery redirect. |

<!-- markdownlint-disable MD049 -->

---

*Last Updated: 2026-10-19* | *Last Reviewed: 2026-10-19*
