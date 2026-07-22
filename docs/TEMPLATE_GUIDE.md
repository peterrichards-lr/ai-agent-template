# Template Architecture, Design Patterns & Language Customization Guide

Welcome to the **AI Agent Development Quickstart Template**. This document outlines why you and your engineering team should adopt this template, the core **AI Agent Design Patterns** integrated into its architecture, and step-by-step instructions for customizing the repository for your target programming language.

---

## Why Use This Template?

Developing software with advanced AI coding agents (such as Antigravity, Claude, Gemini, ChatGPT, Cursor, etc.) offers immense velocity—but without structured governance, agent workflows quickly break down due to:
- **Prompt & Context Bloat**: Loading massive monolithic system prompts exhausts agent context windows and leads to missed instructions.
- **Stateless Loss Between Sessions**: Agents forget architectural constraints, roadmap priorities, and completed work when chat sessions reset.
- **Hallucinated Logic & Unverified Code**: Agents claiming success without running test suites or checking compiler errors.
- **Accidental Destruction & Secret Leaks**: Agents accidentally force-pushing, running destructive commands, or exposing plain-text API credentials.
- **Documentation Decay**: Documentation falling out of sync as AI agents write and refactor code.

This template solves these failure modes out of the box, providing a standardized, production-ready environment for **AI-Human Pair Programming** in **Go, Python, Rust, Java, TypeScript/Node.js, C++, and Liferay**.

---

## Catalog of AI Agent Design Patterns Implemented

### 1. Decoupled Skill Routing (Context-Window Optimization)
- **Problem**: Monolithic system prompts consume thousands of tokens on every message, confusing the agent.
- **Pattern**: `AGENTS.md` acts as a lightweight routing table. Specific operational directives are isolated inside modular `.agents/skills/<skill>/SKILL.md` files. The agent dynamically loads only the skill relevant to its active task (e.g., loading `unit-testing` only during verification).

### 2. Session-Agnostic Persistent State Engine (`GEMINI.md`)
- **Problem**: AI agent context resets when a new conversation begins.
- **Pattern**: `GEMINI.md` serves as a persistent state file tracking project goals, active tasks, completed milestones, roadmap priorities, and rules of engagement. Agents inspect and update `GEMINI.md` before starting work and after completing milestones.

### 3. Logic-First Planning & Predictive Failure Analysis
- **Problem**: AI agents diving into multi-file code modifications prematurely, creating fragile or broken diffs.
- **Pattern**: Before modifying code, the agent outputs a structured `implementation_plan.md` artifact specifying proposed file edits and open questions. It appends a **Predictive Failure Analysis** detailing two edge cases or failure modes and how the code handles them.

### 4. Human-in-the-Loop Verification Gates
- **Problem**: Unchecked agent execution leading to unintended production deployments, database purges, or leaked credentials.
- **Pattern**: High-risk operations (deployments, database drops, secrets generation, force pushes, opening PRs) trigger mandatory approval gates where the agent must stop, request human verification, and wait.

### 5. Empirical Test-Driven Verification Gate
- **Problem**: Agents declaring success ("I have fixed the bug") without running the compiler or test suite.
- **Pattern**: Agents are forbidden from claiming completion based on file edits alone. They must execute non-interactive test commands (`go test`, `pytest`, `cargo test`, `mvn test`) and verify clean output before concluding work.

### 6. Automated Documentation Hygiene & Decay Prevention
- **Problem**: Documentation staleness as code evolves.
- **Pattern**: All `.md` documents maintain standardized footer timestamps (`*Last Updated* | *Last Reviewed*`). Zero-dependency Python tools (`append_timestamps.py` and `check_docs_review.py`) automatically verify and refresh documentation hygiene on every commit.

### 7. Non-Interactive CLI Tool Boundaries & ReAct Reasoning
- **Problem**: CLI tools getting stuck waiting for interactive prompts (e.g. `[y/N]`).
- **Pattern**: Enforces non-interactive flags (`-y`, `--non-interactive`, `--batch`, `-n`) across all terminal invocations and requires ReAct reasoning (Intent → Tool Selection → Expected Outcome) before tool execution.

### 8. GitHub Issue & Task Plan Synchronization
- **Problem**: Disconnect between agent development tasks and team issue trackers.
- **Pattern**: Standardized issue templates (Feature, Bug, Tech Debt), mandatory PR issue linking (`Closes #<issue>`), GitHub Actions CI quality gates, and automated task plan sync via `gh_issue_sync.py`.

### 9. Immediate Technical Debt Governance
- **Problem**: Minor technical debt accumulating unnoticed during agent refactoring.
- **Pattern**: Agents log technical debt immediately to GitHub Issues (`--label "tech-debt"`) across 10 catalogued categories: *Code Smells, Duplication, Over-complexity, Fragile Coupling, Missing Safety Guards, Missing Tests, Security Hygiene, Deprecated Patterns, Config Drift, Documentation Debt*.

### 10. Multi-Agent Subagent Delegation & Asynchronous Synthesis
- **Problem**: Large codebase surveys or parallel research blocking the primary developer agent.
- **Pattern**: Delegates background exploration or static analysis to specialized subagents, synthesizing results asynchronously without polling.

---

## Language Customization Guide

When bootstrapping this template for a specific programming language, follow these ecosystem customization steps:

### 1. Go (`--lang go`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-service" --lang go --clean-template`
- **Source Layout**: Create `go.mod` in project root (`go mod init my-service`) and place source packages in `pkg/` or `cmd/`.
- **Pre-Commit Hooks**: Append `gofmt` and `golangci-lint` to `.pre-commit-config.yaml`.
- **Test Command**: Ensure `.agents/skills/unit-testing/SKILL.md` specifies `go test -v -race ./...`.

### 2. Python (`--lang python`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-app" --lang python --clean-template`
- **Source Layout**: Create `pyproject.toml` or `requirements.txt` and place packages in `src/`.
- **Pre-Commit Hooks**: Append `ruff` (`ruff check --fix`) and `mypy` to `.pre-commit-config.yaml`.
- **Test Command**: Ensure `.agents/skills/unit-testing/SKILL.md` specifies `pytest -v --tb=short`.

### 3. Rust (`--lang rust`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-crate" --lang rust --clean-template`
- **Source Layout**: Run `cargo init` in project root to generate `Cargo.toml` and `src/main.rs` / `src/lib.rs`.
- **Pre-Commit Hooks**: Append `cargo fmt --check` and `cargo clippy -- -D warnings` to `.pre-commit-config.yaml`.
- **Test Command**: Ensure `.agents/skills/unit-testing/SKILL.md` specifies `cargo test --quiet`.

### 4. Java / Kotlin (`--lang java`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-java-service" --lang java --clean-template`
- **Source Layout**: Setup standard Maven (`pom.xml`) or Gradle (`build.gradle`) structure under `src/main/java` and `src/test/java`.
- **Pre-Commit Hooks**: Append `checkstyle` or SpotBugs hooks to `.pre-commit-config.yaml`.
- **Test Command**: Ensure `.agents/skills/unit-testing/SKILL.md` specifies `mvn test -B` or `./gradlew test --no-daemon`.

### 5. TypeScript / Node.js (`--lang node`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-node-app" --lang node --clean-template`
- **Source Layout**: Create `package.json` and `tsconfig.json` placing source code in `src/`.
- **Pre-Commit Hooks**: Append `eslint` and `prettier` to `.pre-commit-config.yaml`.
- **Test Command**: Ensure `.agents/skills/unit-testing/SKILL.md` specifies `npm test -- --ci` or `npx vitest run`.

### 6. Liferay Client Extensions (`--lang liferay`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-cx-project" --lang liferay --clean-template`
- **Source Layout**: Maintain `client-extension.yaml` at root and place microservices/assets in dedicated folders.
- **Rules Alignment**: Enforce `Liferay.authToken` usage (no hardcoded secrets) and LDM integration commands.

---

## Included Skill Modules

| Skill Directory | Purpose & Design Pattern |
| :--- | :--- |
| **`reflection-and-planning`** | Implements Logic-First Planning, `implementation_plan.md` artifacts, Predictive Failure Analysis, and approval loops. |
| **`human-in-the-loop`** | Enforces safety gates for deployments, database drops, plain-text secret prohibitions, and visual diff approvals. |
| **`coding-standards`** | Mandates DRY code discovery (`grep_search`), self-documenting code, defensive safety guards, and language idiom alignment. |
| **`unit-testing`** | Enforces test-driven development, empirical verification gates, non-interactive execution, and prohibits superficial test deletion. |
| **`documentation`** | Governs timestamp footers (`*Last Updated* \| *Last Reviewed*`), post-feature doc updates, and staleness policy checks. |
| **`github-workflow`** | Standardizes `gh` CLI usage, forces PRs to link `Closes #<issue>`, logs tech-debt, and cleans up historical CI failures. |
| **`tool-use-react`** | Enforces reasoning before tool activation, non-interactive flags, and asynchronous task lifecycle management. |
| **`multi-agent-orchestration`** | Governs subagent delegation criteria, clear prompt framing, and asynchronous result synthesis. |

---

## Template Instantiation & Cleanup

When initializing a new repository from this template:

```bash
python3 scripts/bootstrap_template.py --name "my-awesome-service" --lang go --clean-template
```

The bootstrapper script will:
1. Generate a clean project `README.md` describing your application.
2. Remove this template-only guide (`docs/TEMPLATE_GUIDE.md`).
3. Seed `GEMINI.md` with initial project goals and language stack.
4. Run `append_timestamps.py` and install Git pre-commit quality gates.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
