# AI Agent Development Quickstart Template

A production-ready, language-agnostic template repository designed to accelerate **AI Agent-Assisted Software Development**.

Whether you are building in **Go**, **Python**, **Rust**, **Java**, **TypeScript / Node.js**, **C++**, or **Liferay**, this repository provides the structural foundation, active agent constraints, modular skill rules, state management, and automated quality gates required for seamless pair programming with AI agents (such as Antigravity, Claude, Gemini, ChatGPT, etc.).

---

## Key Features

- 🧠 **Context-Optimized Agent Routing (`AGENTS.md`)**: Decouples agent rules into domain-specific skill files (`.agents/skills/`), preventing prompt bloat and context token exhaustion.
- 🔀 **Provider Discovery Redirects (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`)**: Lightweight redirects ensuring all AI providers load canonical rules from `AGENTS.md`.
- 📌 **Persistent Scratchpad State (`.agent-state.md`)**: Shared gitignored scratchpad tracking project status, active goals, and roadmap priorities across provider switches. Seeded from the tracked template `.agents/templates/agent-state.md` during bootstrap, so a fresh clone always starts with one.
- 🛡️ **Language-Agnostic Quality Gates (`.pre-commit-config.yaml`)**: Out-of-the-box pre-commit configuration supporting secret scanning (`detect-secrets`, `gitleaks`), markdown link validation, document review policies, and modular linting for Go, Python, Rust, Java, and Node.js.
- ⏱️ **Automated Documentation Hygiene**: Zero-dependency Python 3 tools (`append_timestamps.py` and `check_docs_review.py`) to enforce timestamp footers (`*Last Updated* | *Last Reviewed*`) and prevent documentation decay.
- 🧰 **One Task Runner Vocabulary (`Makefile`)**: `make setup`, `make lint`, `make test`, `make docs`, `make verify`, `make push` and `make help` mean the same thing in Go, Python, Rust, Java, Node, C++ and Liferay projects. Only a marked profile block varies, filled in by the bootstrapper. `make verify` is invoked *by* `ci.yml`, so "did I break CI" is one local command and the two cannot drift.
- ⚙️ **Project Bootstrapper (`scripts/bootstrap_template.py`)**: One-command initialization script that customizes the template for your chosen programming language stack, installs git hooks, and seeds project metadata. `--dry-run` previews every mutation before anything is written.
- 🩺 **Post-Bootstrap Verification (`scripts/doctor.py`)**: Runs as bootstrap's final step and as a pre-commit hook, exiting non-zero with the file and line of every surviving template placeholder, plus checks that `.claude/skills` resolved to a directory and the agent scratchpad was seeded. A missed substitution fails loudly instead of shipping an unsubstituted test-command placeholder into your agent rules.
- 🏗️ **Per-Language CI Profiles (`.agents/templates/ci/`)**: `--lang go` installs a workflow that builds Go, not one that runs this template's Python self-tests. Every profile calls the same `Makefile` verbs, so no ecosystem command is ever restated in YAML. The always-on `Code & Documentation Quality Verification` job carries the doc and lint checks; only the `Build & Test` job sits behind a paths filter, paired with a same-named skip job so a documentation-only pull request still reports the context instead of deadlocking on it, and a *failed* filter fails loudly rather than silently skipping both.
- 🚀 **GitHub CI & Governance (`.github/`)**: GitHub Actions workflow (`ci.yml`), GitHub Issue Forms (Feature, Bug, Tech Debt) with typed required fields and a chooser (`ISSUE_TEMPLATE/config.yml`) that disables blank issues, a commented `CODEOWNERS` stub, and a PR template enforcing task linking (`Closes #<issue>`).
- 🔎 **Optional Security Scanning (`.github/workflows/security-scan.yml`, `.semgrep.yaml`)**: Non-blocking Semgrep SAST plus `actions/dependency-review-action` on pull requests, with a commented `.semgrep.yaml` stub for turning a prose coding rule into a mechanically enforced one. Neither job is a required status check, so a new project is never broken on day one by a third-party finding.
- 🤝 **Community Health Stubs (`CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `.editorconfig`)**: Contributor Covenant v2.1, a Keep a Changelog seed, and a shared editor baseline (UTF-8, LF, final newline, trimmed trailing whitespace) that keeps editors from fighting the `trailing-whitespace` and `end-of-file-fixer` pre-commit hooks. Owner and contact placeholders are filled in by the bootstrapper.

---

## Quickstart

### 1. Initialize a New Repository from this Template

Use this repository as a template on GitHub, or clone it locally:

```bash
git clone https://github.com/peterrichards-lr/ai-agent-template.git my-new-project
cd my-new-project
```

> [!NOTE]
> **Windows Users (`core.symlinks`)**: Ensure symlink creation is enabled during clone so `.claude/skills` is materialized as a true directory link rather than a text file:
>
> ```bash
> git clone -c core.symlinks=true https://github.com/peterrichards-lr/ai-agent-template.git my-new-project
> ```

### 2. Run the Bootstrap Script

Run the language-agnostic bootstrapper to configure your project details and setup pre-commit quality gates.

> [!IMPORTANT]
> `--name`, `--repo-owner` and `--conduct-email` are **required**. Every one of them is
> substituted into files the agent rules and community health docs depend on, and bootstrap
> finishes by running `scripts/doctor.py`, which fails on any placeholder left unresolved.
> Declaring them required means a missing value is an argparse usage error *before* any file
> is touched, rather than a failed verification after a dozen files have been rewritten.

```bash
# Preview every planned mutation without changing anything
python3 scripts/bootstrap_template.py --name "my-awesome-app" --lang go \
  --repo-owner "my-org" --conduct-email "conduct@example.com" --dry-run

# Apply it
python3 scripts/bootstrap_template.py --name "my-awesome-app" --lang go \
  --repo-owner "my-org" --conduct-email "conduct@example.com"

# Optionally add GitHub SEO metadata and drop the template's own meta docs and self-tests
python3 scripts/bootstrap_template.py --name "my-awesome-app" --lang go \
  --repo-owner "my-org" --conduct-email "conduct@example.com" --clean-template \
  --repo-desc "High-performance Go service built with AI Agent pair programming" \
  --repo-topics "ai-agent,developer-tools,go"
```

The bootstrapper will:

1. Update project configuration files (`README.md`, `.agent-state.md`, `AGENTS.md`).
2. Fill the `Makefile`'s language profile block in, so `make test` runs your stack's command.
3. Generate language-specific `.gitignore` and `.pre-commit-config.yaml` rules.
4. Verify or create the `.claude/skills` auto-discovery symlink.
5. Seed the community health stubs (`CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/config.yml`) with your project name, the GitHub owner (`--repo-owner`) and the Code of Conduct contact (`--conduct-email`).
6. With `--clean-template`, remove the template's own meta docs and Python scaffolding (`docs/TEMPLATE_GUIDE.md`, `tests/`, and -- outside `--lang python` -- `src/__init__.py` and `requirements-python.txt`). This is the **only** way to request those deletions; there is no `-y` shortcut.
7. With `--docs-site`, enable the optional MkDocs Material documentation site (`mkdocs.yml`, `.github/workflows/docs.yml`, `requirements-docs.txt`) and arm its GitHub Pages deploy; without it, `--clean-template` removes that scaffold entirely. See [docs/TEMPLATE_GUIDE.md](docs/TEMPLATE_GUIDE.md).
8. Initialize local Git pre-commit hooks.
9. Inject initial documentation timestamps.
10. Configure GitHub Repository Description and SEO Topic Tags via `gh` CLI.
11. Run `scripts/doctor.py` and **fail** if any placeholder survived.

Re-run the verification at any time:

```bash
python3 scripts/doctor.py
```

### 3. Use the Task Runner

Everything after bootstrap goes through seven verbs that mean the same thing in every
language stack, so an agent never has to work out which ecosystem's commands apply:

```bash
make help      # self-documenting target list (the default goal)
make setup     # install dev dependencies and the pre-commit git hooks
make lint      # pre-commit run --all-files, plus this stack's linters
make test      # this stack's non-interactive test command
make docs      # refresh and verify documentation timestamp footers
make verify    # lint + test + docs -- the full local quality gate
make push MESSAGE="feat(scope): what changed"
```

`make verify` is **exactly** what `.github/workflows/ci.yml` runs: the workflow invokes
this target rather than restating the commands, so the two cannot drift and "did I break
CI?" is one local command. The ecosystem's real invocation lives in one marked block in
the `Makefile`, which `scripts/bootstrap_template.py --lang <stack>` fills in — it is
yours to edit afterwards.

`make push` is the guarded git entrypoint (`scripts/agent_push.py`). It refuses a no-op
push, refuses to commit while tracked files are still modified but unstaged, rejects a
flag-shaped commit message such as a bare `-m`, and runs the pre-commit gate instead of
bypassing it. `--force-with-lease` is the sanctioned force form
(`make push PUSH_ARGS=--force-with-lease`); bare `--force` is denied client-side in
`.claude/settings.json`.

### Windows Notes

Two things need attention on a Windows checkout.

**Symlinks (`core.symlinks`)**: see the clone command above — without it `.claude/skills`
is materialized as a text file and agent skill discovery silently finds nothing.
`scripts/doctor.py` checks for this explicitly.

> [!NOTE]
> **Make**: GNU Make is not installed by default on Windows, so `make verify` needs it
> provided. This is an accepted, documented limitation rather than a papered-over one:
> Make is the lowest common denominator that agents already know, and shipping a second
> PowerShell shim would recreate the two-vocabularies problem the task runner exists to
> remove. Install it through Git Bash, MSYS2, WSL, or `winget install GnuWin32.Make`.
> Everything the targets call is Python 3 and runs natively either way, so the individual
> commands remain available if you would rather not install Make.

---

## Repository Structure

```text
.
├── AGENTS.md                          # Master routing index for AI agent skills
├── GEMINI.md                          # Discovery redirect to AGENTS.md (Gemini CLI)
├── CLAUDE.md                          # Discovery redirect to AGENTS.md (Claude CLI)
├── .cursorrules                       # Discovery redirect to AGENTS.md (Cursor IDE)
├── .windsurfrules                     # Discovery redirect to AGENTS.md (Windsurf IDE)
├── .claude/                           # Claude Code configuration & discovery
│   └── skills                         # Symlink -> ../.agents/skills
├── .agent-state.md                    # Gitignored persistent task scratchpad (seeded by bootstrap)
├── CONTRIBUTING.md                    # Guidelines for human & AI agent contributors
├── CODE_OF_CONDUCT.md                 # Contributor Covenant v2.1 (adopter-customisable stub)
├── CHANGELOG.md                       # Keep a Changelog release history (adopter stub)
├── SECURITY.md                        # Vulnerability disclosure policy
├── README.md                          # This file
├── LICENSE                            # MIT License
├── Makefile                           # Task runner: setup/lint/test/docs/verify/push/help
├── .gitignore                         # Language-agnostic ignore rules
├── .editorconfig                      # Shared editor baseline (UTF-8, LF, final newline)
├── .pre-commit-config.yaml            # Pre-commit quality gate configuration
├── .semgrep.yaml                      # Project-specific Semgrep rules (commented stub)
├── .github/                           # CI workflows & GitHub templates
│   ├── copilot-instructions.md        # Discovery redirect to AGENTS.md (GitHub Copilot)
│   ├── CODEOWNERS                     # Commented ownership stub (see require_code_owner_review)
│   ├── PULL_REQUEST_TEMPLATE.md       # PR template with issue linking checks
│   ├── ISSUE_TEMPLATE/                # Structured GitHub Issue Forms
│   │   ├── bug_report.yml             # Bug form: description, repro, expected behaviour
│   │   ├── feature_request.yml        # Feature form: problem, solution, impact
│   │   ├── tech_debt.yml              # Tech debt form: canonical 10-category dropdown
│   │   └── config.yml                 # Issue chooser: blank issues off, contact links
│   ├── workflows/ci.yml               # GitHub Actions CI workflow (installed from a CI profile)
│   └── workflows/security-scan.yml    # Optional non-blocking Semgrep & dependency review
├── .agents/skills/                    # Modular skill instructions for AI agents
│   ├── no-assumptions/                # Always-active anti-hallucination protocol
│   ├── reflection-and-planning/       # Logic-first planning & approval loops
│   ├── human-in-the-loop/             # Safety verification gates for risky operations
│   ├── coding-standards/              # DRY code, self-documenting code & error safety
│   ├── unit-testing/                  # TDD & non-interactive test rules
│   ├── e2e-verification/              # Real-app evidence when unit tests aren't proof
│   ├── documentation/                 # Timestamp & doc maintenance rules
│   ├── github-workflow/               # Issue sync, PR review feedback loop & CI cleanup
│   ├── tool-use-react/                # ReAct reasoning & CLI command boundaries
│   ├── multi-agent-orchestration/     # Subagent delegation directives
│   ├── rule-adherence/                # Self-verification & checkable artifact rules
│   ├── release-management/            # Semantic versioning & release auditing
│   └── template-sync/                 # Upstream drift checks & the bidirectional contract
├── .agents/templates/                 # Tracked seed files copied into place by bootstrap
│   ├── agent-state.md                 # Starter scratchpad seed for .agent-state.md
│   ├── template-ref.md                # Seed for the committed .agents/TEMPLATE_REF.md checkpoint
│   └── ci/                            # Per-language CI workflow profiles (one per --lang choice)
├── scripts/                           # Portable Python 3 helper utilities
│   ├── append_timestamps.py           # Injects markdown footer timestamps
│   ├── check_docs_review.py           # Validates doc freshness & review age
│   ├── bootstrap_template.py          # Project initializer script
│   ├── agent_push.py                  # Guarded commit-and-push behind `make push`
│   ├── check_template_drift.py        # Compares this repo against the upstream template
│   ├── doctor.py                      # Post-bootstrap placeholder & structure verification
│   └── gh_issue_sync.py               # GitHub issue & task plan helper
├── requirements-dev.txt               # Language-agnostic agent tooling & quality gate deps
├── requirements-python.txt            # Python-project test deps (removed for other stacks)
└── src/                               # Starter source directory (Python marker removed for other stacks)
```

---

## AI Agent Workflow & Interaction Model

When interacting with an AI coding assistant in this repository, the agent will automatically follow the **Rules of Engagement** specified in `AGENTS.md` and `.agent-state.md`:

1. **State Persistence**: Before making structural changes, the agent updates `.agent-state.md` to persist current context.
2. **Context-Driven Skill Activation**: The agent loads only the relevant `.agents/skills/<skill>/SKILL.md` file required for the current task.
3. **Logic-First Planning**: For complex changes, the agent presents an implementation plan before modifying files.
4. **Documentation Sync**: After writing code, the agent runs `scripts/append_timestamps.py` and `scripts/check_docs_review.py` to maintain documentation hygiene.
5. **Quality Verification**: All changes are validated using non-interactive test commands before marking a task complete.

---

## License

This template is open source and available under the [MIT License](LICENSE).

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
