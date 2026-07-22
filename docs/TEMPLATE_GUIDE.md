# Template Architecture & AI Agent Guide

This document contains meta-documentation specific to the **AI Agent Development Quickstart Template**. It is intended for template maintainers and developers setting up the template repo.

> [!NOTE]
> **Template-Only Document**: When you run `python3 scripts/bootstrap_template.py --clean-template` to initialize a new repository, this template guide is archived/cleaned up so your new repository contains only your project-specific documentation.

---

## 1. Design Philosophy

The template is built around four core principles designed to maximize AI coding agent productivity while preventing common pitfalls:

### A. Context Optimization via Modular Routing (`AGENTS.md` & `.agents/skills/`)
Monolithic prompt instructions degrade AI agent performance and waste context window tokens. By keeping `AGENTS.md` as a lightweight table of contents and moving detailed instructions into `.agents/skills/<skill>/SKILL.md`, the AI agent only loads full skill rules when actively needed.

### B. Session State Persistence (`GEMINI.md`)
AI coding assistants are stateless by default across conversation restarts. `GEMINI.md` provides a persistent state engine tracking active tasks, milestones, roadmap priorities, active constraints, and technical debt registries.

### C. Language-Agnostic Core with Portable Tools (`scripts/`)
All helper tools (`append_timestamps.py`, `check_docs_review.py`, `bootstrap_template.py`, `gh_issue_sync.py`) are written in standard Python 3 using built-in libraries. They run seamlessly across macOS, Linux, and Windows without external dependencies.

### D. Automated Quality & Security Gates (`.pre-commit-config.yaml` & GitHub Actions)
Pre-commit hooks and GitHub Actions workflows enforce formatting, secret scanning (`detect-secrets`, `gitleaks`), markdown link validation, and document staleness checks before code can be merged.

---

## 2. Included Skill Modules

| Skill Directory | Purpose & Rules |
| :--- | :--- |
| `reflection-and-planning` | Enforces logic-first planning (`implementation_plan.md`), failure analysis (2 edge cases), and user approval gates before multi-file edits. |
| `human-in-the-loop` | Mandates human verification before high-risk operations (deployments, database drops, secrets generation, opening PRs). |
| `coding-standards` | Enforces DRY code discovery via `grep_search`, self-documenting code, error tracing, and language-specific idiom alignment. |
| `unit-testing` | Requires test coverage confirmation, empirical test execution before claiming completion, and non-interactive command flags. |
| `documentation` | Mandates timestamp footers (`*Last Updated* | *Last Reviewed*`) and runs staleness checks after feature execution. |
| `github-workflow` | Standardizes `gh` CLI usage, forces PRs to link `Closes #<issue>`, and automates CI run cleanup. |
| `tool-use-react` | Enforces ReAct reasoning patterns before tool calls and non-interactive CLI boundaries (`-y`, `--non-interactive`). |
| `multi-agent-orchestration` | Governs subagent delegation, task framing, and async result synthesis. |

---

## 3. How Template Cleanup Works

When a developer clones this template and runs:

```bash
python3 scripts/bootstrap_template.py --name "my-service" --lang go --clean-template
```

The bootstrapper script will:
1. Generate a clean, project-specific `README.md` describing your application.
2. Remove or archive `docs/TEMPLATE_GUIDE.md`.
3. Update `GEMINI.md` with your initial project metadata.
4. Run `append_timestamps.py` to ensure all docs have current footers.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
