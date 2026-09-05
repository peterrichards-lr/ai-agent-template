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

### 2. Provider-Agnostic Routing & Persistent Scratchpad (`.agent-state.md`)
- **Problem**: AI agent context resets when a new conversation begins, or context is fragmented across provider-specific files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`).
- **Pattern**: Provider discovery files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`) exist solely as lightweight redirects to `AGENTS.md`. Active in-flight state is managed in `.agent-state.md` (gitignored), ensuring seamless context preservation across AI provider switches (Gemini, Claude, Cursor, Copilot, Windsurf, etc.). Because that file is gitignored, it cannot ship with a clone: `scripts/bootstrap_template.py` seeds it from the tracked template `.agents/templates/agent-state.md`, so a freshly bootstrapped project always has the scratchpad the rules refer to. The seed deliberately carries no technical debt table -- debt is tracked solely as `tech-debt` GitHub issues (`.agents/skills/github-workflow/SKILL.md` rule 4).

### 3. Logic-First Planning & Predictive Failure Analysis
- **Problem**: AI agents diving into multi-file code modifications prematurely, creating fragile or broken diffs.
- **Pattern**: Before modifying code, the agent writes out a structured implementation plan specifying proposed file edits and open questions, using whatever planning mechanism its own toolset provides. It appends a **Predictive Failure Analysis** detailing two edge cases or failure modes and how the code handles them.

### 4. Human-in-the-Loop Verification Gates & Client-Side Harness Enforcement
- **Problem**: Unchecked agent execution leading to unintended production deployments, database purges, or leaked credentials. Prose rules alone in skill files do not physically prevent agents from executing destructive commands locally.
- **Pattern**: Dual-layer defense: High-risk operations (deployments, database drops, secrets generation, force pushes, merging to `main`) trigger mandatory human approval gates in `.agents/skills/human-in-the-loop/SKILL.md`. On the client side, `.claude/settings.json` enforces deterministic command interception (`deny` for `rm -rf`, `git push --force`, `docker system prune`, `DROP DATABASE`, `gh repo delete`; `ask` for `gh pr merge`, `git tag`, `gh release create`). This serves as the client-side counterpart to server-side branch protection rulesets (`docs/BRANCH_PROTECTION.md`): the same defense-in-depth argument at both ends of the development pipe.

### 5. Empirical Test-Driven Verification Gate
- **Problem**: Agents declaring success ("I have fixed the bug") without running the compiler or test suite, or asserting tautologies on tests that pass vacuously without proving they had the power to fail.
- **Pattern**: Agents are forbidden from claiming completion based on file edits alone, or claiming verification from an immediate pass. For bug fixes, the reproduction test must be observed and cited failing red before implementing the fix; for new features, logic must be mutated/disabled to confirm the test fails red before concluding. In both cases, the agent must revert any mutation, run `make test` (or `make verify` for the full gate -- the ecosystem's actual command lives in the `Makefile` language profile, stated once), and document the red-to-green transition before concluding work. For pure refactorings, the existing test suite serves as the invariant baseline that must stay continuously green.

### 6. Automated Documentation Hygiene & Decay Prevention
- **Problem**: Documentation staleness as code evolves.
- **Pattern**: All `.md` documents maintain standardized footer timestamps (`*Last Updated* | *Last Reviewed*`). Zero-dependency Python tools (`append_timestamps.py` and `check_docs_review.py`) automatically verify and refresh documentation hygiene on every commit.

### 7. Non-Interactive CLI Tool Boundaries & ReAct Reasoning
- **Problem**: CLI tools getting stuck waiting for interactive prompts (e.g. `[y/N]`).
- **Pattern**: Enforces non-interactive flags (`-y`, `--non-interactive`, `--batch`, `-n`) across all terminal invocations and requires ReAct reasoning (Intent → Tool Selection → Expected Outcome) before tool execution.

### 8. GitHub Issue & Task Plan Synchronization
- **Problem**: Disconnect between agent development tasks and team issue trackers.
- **Pattern**: GitHub Issue Forms (`bug_report.yml`, `feature_request.yml`, `tech_debt.yml`) with typed, individually required fields rather than freeform Markdown prompts agents delete; mandatory PR issue linking (`Closes #<issue>`), GitHub Actions CI quality gates, and automated task plan sync via `gh_issue_sync.py`. Each form keeps at most four required fields -- a form demanding a page of mandatory input for a one-line bug gets routed around rather than filled in.

### 9. Immediate Technical Debt Governance
- **Problem**: Minor technical debt accumulating unnoticed during agent refactoring.
- **Pattern**: Agents log technical debt immediately to GitHub Issues (`--label "tech-debt"`) across 10 catalogued categories. The taxonomy has exactly one home -- the required `Category` dropdown in [`.github/ISSUE_TEMPLATE/tech_debt.yml`](../.github/ISSUE_TEMPLATE/tech_debt.yml) -- which `.agents/skills/github-workflow/SKILL.md` rule 4 mirrors for command-line filing and `tests/test_issue_templates.py` holds in step. This page deliberately does not restate the list: a third hand-maintained copy is a third thing to forget to update.

### 10. Multi-Agent Subagent Delegation & Asynchronous Synthesis
- **Problem**: Large codebase surveys or parallel research blocking the primary developer agent.
- **Pattern**: Delegates background exploration or static analysis to specialized subagents, synthesizing results asynchronously without polling.

### 11. One Task Runner Vocabulary Across Every Stack
- **Problem**: Each ecosystem's commands get restated in `AGENTS.md`, `CONTRIBUTING.md`, the skill files and the CI workflow. The copies drift, and an agent that reads the wrong one runs the wrong command -- or, in Go's case, an EDR-unsafe one.
- **Pattern**: A root `Makefile` exposes seven fixed verbs (`setup`, `lint`, `test`, `docs`, `verify`, `push`, `help`) in every language. Only a marked profile block varies, filled in by `scripts/bootstrap_template.py --lang <stack>`. `make verify` is invoked *by* `.github/workflows/ci.yml`, so local and CI gates cannot drift. A knock-on effect: once the sanctioned Go test path is `make test` rather than something starting with `go test`, `.claude/settings.json` can deny `Bash(go test*)` wholesale -- deny beats allow, and "`go test*` except `-c`" is inexpressible in the permission patterns.

---

## Language Customization Guide

When bootstrapping this template for a specific programming language, follow these ecosystem
customization steps. In every case the test command itself is **not** restated below: it lives in
the `Makefile`'s language profile block, which `scripts/bootstrap_template.py --lang <stack>` fills
in, and every stack is driven through the same seven verbs:

| Target | Contract |
| :--- | :--- |
| `make setup` | Install dev dependencies and the pre-commit Git hooks. |
| `make lint` | `pre-commit run --all-files` plus the stack's linters. |
| `make test` | The stack's non-interactive test command. |
| `make docs` | `append_timestamps.py` then `check_docs_review.py`. |
| `make verify` | `lint` + `test` + `docs` -- exactly what `.github/workflows/ci.yml` runs. |
| `make push` | Guarded commit-and-push (`scripts/agent_push.py`). |
| `make help` | Self-documenting target list; the default goal. |

That is the point of the task runner: an agent asked to verify its work runs `make verify`
regardless of the stack, and `AGENTS.md`, `CONTRIBUTING.md` and this guide stop carrying their own
drifting copies of `pytest` / `cargo test` / `npm test`. Edit the profile block freely after
bootstrap -- it is your project's, not generated code.

> [!NOTE]
> **Make on Windows.** GNU Make is not present on a default Windows install. This is an accepted
> limitation rather than a papered-over one: Make is the lowest common denominator that agents
> already know, and shipping a second shim would recreate the two-vocabularies problem the task
> runner exists to remove. Install it via Git Bash, MSYS2, WSL, or `winget install GnuWin32.Make`.
> The helper scripts the targets call are all Python 3 and run natively either way.

### 1. Go (`--lang go`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-service" --lang go --clean-template --repo-owner "my-org" --conduct-email "conduct@example.com"`
- **Source Layout**: Create `go.mod` in project root (`go mod init my-service`) and place source packages in `pkg/` or `cmd/`.
- **Pre-Commit Hooks**: Append `gofmt` and `golangci-lint` to `.pre-commit-config.yaml`.
- **EDR-Safe Testing**: The Go profile exports `GOTMPDIR` with `:=` and guards it with an
  `edr-guard` target before building. `GOTMPDIR` -- not `-o` -- decides where an unsigned test
  binary first appears on disk, because the toolchain links inside it and only then moves the
  file to the `-o` path. Because `make test` no longer starts with `go test`, bootstrap denies
  `Bash(go test*)` wholesale in `.claude/settings.json`. See `.agents/skills/unit-testing/SKILL.md`.

### 2. Python (`--lang python`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-app" --lang python --clean-template --repo-owner "my-org" --conduct-email "conduct@example.com"`
- **Source Layout**: Create `pyproject.toml` or `requirements.txt` and place packages in `src/`.
- **Pre-Commit Hooks**: Append `ruff` (`ruff check --fix`) and `mypy` to `.pre-commit-config.yaml`.

### 3. Rust (`--lang rust`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-crate" --lang rust --clean-template --repo-owner "my-org" --conduct-email "conduct@example.com"`
- **Source Layout**: Run `cargo init` in project root to generate `Cargo.toml` and `src/main.rs` / `src/lib.rs`.
- **Pre-Commit Hooks**: `make lint` already runs `cargo fmt --check` and `cargo clippy -- -D warnings`.

### 4. Java / Kotlin (`--lang java`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-java-service" --lang java --clean-template --repo-owner "my-org" --conduct-email "conduct@example.com"`
- **Source Layout**: Setup standard Maven (`pom.xml`) or Gradle (`build.gradle`) structure under `src/main/java` and `src/test/java`.
- **Pre-Commit Hooks**: Append `checkstyle` or SpotBugs hooks to `.pre-commit-config.yaml`.

### 5. TypeScript / Node.js (`--lang node`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-node-app" --lang node --clean-template --repo-owner "my-org" --conduct-email "conduct@example.com"`
- **Source Layout**: Create `package.json` and `tsconfig.json` placing source code in `src/`.
- **Pre-Commit Hooks**: Append `eslint` and `prettier` to `.pre-commit-config.yaml`.

### 6. C++ (`--lang cpp`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-engine" --lang cpp --clean-template --repo-owner "my-org" --conduct-email "conduct@example.com"`
- **Source Layout**: Maintain `CMakeLists.txt` at root; `make setup` configures the `build/` tree.
- **Pre-Commit Hooks**: Append `clang-format` and `clang-tidy` to `.pre-commit-config.yaml`.

### 7. Liferay Client Extensions (`--lang liferay`)
- **Initialization**: `python3 scripts/bootstrap_template.py --name "my-cx-project" --lang liferay --clean-template --repo-owner "my-org" --conduct-email "conduct@example.com"`
- **Source Layout**: Maintain `client-extension.yaml` at root and place microservices/assets in dedicated folders.
- **Rules Alignment**: Enforce `Liferay.authToken` usage (no hardcoded secrets) and LDM integration commands.

---

## Included Skill Modules

| Skill Directory | Purpose & Design Pattern |
| :--- | :--- |
| **`no-assumptions`** | Always active. Forbids technical claims not backed by a tool call made in the current session; after a compaction or resume, earlier tool results stop counting as evidence. |
| **`reflection-and-planning`** | Implements Logic-First Planning, written implementation plans, Predictive Failure Analysis, and approval loops. |
| **`human-in-the-loop`** | Enforces safety gates for deployments, database drops, plain-text secret prohibitions, and visual diff approvals. |
| **`coding-standards`** | Mandates DRY code discovery (using the agent's available code-search tool), self-documenting code, defensive safety guards, language idiom alignment, mechanically enforced rules (`.semgrep.yaml`), and scope-sprawl anti-churn limits. |
| **`unit-testing`** | Enforces test-driven development, fail-first verification gates (citing red-to-green empirical evidence), non-interactive execution, and prohibits superficial test deletion. |
| **`e2e-verification`** | Covers changes a green unit suite cannot prove (UI, process/network boundaries, CLI, deployment): what real-system evidence counts, teardown duties, and specific human escalation. |
| **`documentation`** | Governs timestamp footers (`*Last Updated* \| *Last Reviewed*`), post-feature doc updates, and staleness policy checks. |
| **`github-workflow`** | Standardizes `gh` CLI usage, forces PRs to link `Closes #<issue>`, drives the PR review feedback loop (pull review summaries and CI status with `gh pr view`, inline file/line comments with `gh api repos/{owner}/{repo}/pulls/<number>/comments`, close the loop on each one), logs tech-debt, and cleans up historical CI failures. |
| **`tool-use-react`** | Enforces reasoning before tool activation, non-interactive flags, and asynchronous task lifecycle management. |
| **`multi-agent-orchestration`** | Governs subagent delegation criteria, clear prompt framing, and asynchronous result synthesis. |
| **`rule-adherence`** | Addresses agents not reliably following prose rules: re-read before acting, prefer checkable artifacts, and self-correct visibly. |
| **`release-management`** | Governs semantic versioning, release notes, auditing issue closure, and human verification gates. |

---

## Enforcing These Rules, Not Just Documenting Them

Prose rules alone don't reliably bind agent behavior. This template enforces defense-in-depth at both ends of the development pipe:
- **Server-Side Enforcement**: Importable GitHub repository rulesets (`docs/BRANCH_PROTECTION.md`) turn repository governance (PR-only changes to main, required CI checks, issue-linking) into gates no one -- human or agent -- can silently skip.
- **Pattern-Level Enforcement**: Project-specific Semgrep rules (`.semgrep.yaml`, scanned by `.github/workflows/security-scan.yml`) turn a coding rule that a pattern-matcher could check into an enforced one instead of prose an agent can read and still violate. `coding-standards/SKILL.md` directive 5 requires a rule to be added there whenever it is mechanically checkable. The scan is non-blocking (`continue-on-error: true`, not a required status check) so a new rule reports before it gates.
- **Client-Side Enforcement**: Checked-in harness configuration (`.claude/settings.json`) intercepts and denies irreversibly destructive local shell patterns (`rm -rf`, `git push --force`, `docker system prune`, `DROP DATABASE`, `gh repo delete`) and requires interactive confirmation for high-risk operations (`gh pr merge`, `git tag`, `gh release create`).

---

## Template Instantiation & Cleanup

When initializing a new repository from this template:

```bash
python3 scripts/bootstrap_template.py --name "my-awesome-service" --lang go --clean-template \
  --repo-owner "my-org" --conduct-email "conduct@example.com"
```

Add `--dry-run` to print every planned mutation -- file writes, deletions, `gh repo edit`
calls and hook installation -- without applying any of them.

The bootstrapper script will:
1. Generate a clean project `README.md` describing your application.
2. Remove this template-only guide (`docs/TEMPLATE_GUIDE.md`).
3. Remove the template's Python scaffolding (see below).
4. Customize `AGENTS.md` with the project name.
5. Seed the community health stubs with the project name, GitHub owner, and conduct contact.
6. Run `append_timestamps.py` and install Git pre-commit quality gates.
7. Run `scripts/doctor.py` and fail if any placeholder survived.

### Python Scaffolding Removed by `--clean-template`

The template is written in Python and tests itself in Python, so some of its checked-in
scaffolding is Python-specific rather than part of what an adopter needs:

| Path | Removed when | Why |
| :--- | :--- | :--- |
| `tests/` | always | Tests the bootstrapper that has just finished running; dead weight (and broken imports) in the adopter's repository. |
| `src/__init__.py` | `--lang` is not `python` | A Python package marker, meaningless in a Go, Rust, Java or Node project. |
| `requirements-python.txt` | `--lang` is not `python` | Pins `pytest`; irrelevant outside a Python project. |

`requirements-dev.txt` is never removed: it holds only the language-agnostic agent tooling
(`pre-commit`, `detect-secrets`, `actionlint-py`, `PyYAML`) that every adopter's quality
gate depends on, regardless of the project's language.

### Optional Documentation Site (`--docs-site`)

Two of this template's sibling projects outgrew "a folder of Markdown files" and
independently built the same thing: `mkdocs.yml` plus a workflow deploying MkDocs Material
to GitHub Pages, organised on the [Diátaxis](https://diataxis.fr) model. The template
carries that scaffold, but a 200-line utility should not inherit a documentation engine it
never asked for, so it is strictly opt-in:

```bash
python3 scripts/bootstrap_template.py --name "my-awesome-service" --lang go --clean-template \
  --repo-owner "my-org" --conduct-email "conduct@example.com" --docs-site
```

| Path | Without `--docs-site` | With `--docs-site` |
| :--- | :--- | :--- |
| `mkdocs.yml` | removed by `--clean-template` | `site_name`, `site_url` and `repo_url` seeded from `--name`/`--repo-owner` |
| `.github/workflows/docs.yml` | removed by `--clean-template` | the commented `push:` trigger is uncommented, arming the Pages deploy |
| `requirements-docs.txt` | removed by `--clean-template` | kept; installed only by the docs workflow |
| `docs/tutorials/`, `docs/how-to/`, `docs/reference/`, `docs/explanation/` | kept | kept |

Three deliberate choices:

- **The workflow ships dormant.** Its only live trigger is `workflow_dispatch`, so a
  repository that did not opt in never runs it and never assumes GitHub Pages is enabled
  (it is not, on a fresh repository -- set Settings → Pages → Source to "GitHub Actions"
  first). The `push:` trigger ships commented out, between markers `--docs-site`
  uncomments, so a reader can see exactly what enabling it does.
- **The Diátaxis directories survive either way.** Sorting documentation into tutorials,
  how-to guides, reference and explanation is worth doing whether or not it is rendered.
  Where a new page belongs is the decision agents get wrong most often, so the rule lives
  in `.agents/skills/documentation/SKILL.md` and, at length, in `docs/explanation/`.
- **`mkdocs-material` is not in `requirements-dev.txt`.** That file is installed by every
  adopter on every CI run; the docs site owns `requirements-docs.txt` instead, so a project
  without a published site pays nothing for one.

The site home page is generated from `README.md` at build time (`cp README.md
docs/index.md`, run by the workflow and gitignored) so the GitHub landing page and the site
home are one document. Timestamp footers are rendered rather than hidden: they are the
repository's freshness contract, and the published site is where a reader can act on it.

### Post-Bootstrap Verification (`scripts/doctor.py`)

Every bootstrap mutation is a regex substitution or a file copy, and either can miss. The
doctor is the end-state check that turns a silent miss into a loud failure:

- scans the tree for surviving placeholders (`<..._PLACEHOLDER>`, `your-org`, `my-ai-project`)
  and exits 1 listing the file and line of each,
- asserts `.claude/skills` resolves to a **directory** -- on a Windows checkout without
  `core.symlinks`, git materialises it as a text file and agent skill discovery silently
  finds nothing,
- asserts `.agent-state.md` was seeded.

It runs as bootstrap's final step, as the `doctor` pre-commit hook, and in `ci.yml`. This
repository runs it as `--mode template`, which exempts the un-bootstrapped stubs it is
supposed to still carry; bootstrap drops that flag so your repository is checked strictly.

### Community Health & Editor Baseline Stubs

These files ship deliberately short and clearly marked as adopter-customisable:

| File | Purpose | Placeholders |
| :--- | :--- | :--- |
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1. | `<CONDUCT_EMAIL_PLACEHOLDER>` (`--conduct-email`) |
| `CHANGELOG.md` | Keep a Changelog seed feeding the `release-management` skill. | `<GITHUB_OWNER_PLACEHOLDER>` (`--repo-owner`) |
| `.editorconfig` | UTF-8 / LF / final-newline / trimmed-whitespace baseline plus per-language indent rules for every `--lang` stack. Prevents editors from producing commits that the `trailing-whitespace` and `end-of-file-fixer` hooks immediately rewrite. | none |
| `.github/CODEOWNERS` | Fully commented ownership stub. Makes `"require_code_owner_review"` in `.github/rulesets/protect-main-branch.json` a real, flippable switch instead of a reference to a missing file. | `<GITHUB_OWNER_PLACEHOLDER>` (`--repo-owner`) |
| `.github/ISSUE_TEMPLATE/config.yml` | Issue chooser: `blank_issues_enabled: false` plus contact links, steering reports into the structured templates the `github-workflow` skill depends on. | `<GITHUB_OWNER_PLACEHOLDER>` (`--repo-owner`) |

`scripts/doctor.py` runs as bootstrap's final step and **fails** the bootstrap when any of
these placeholders is still live, citing the file and line. Supply `--repo-owner` and
`--conduct-email`, or edit the cited lines by hand and re-run.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
