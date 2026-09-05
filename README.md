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
- ⚙️ **Project Bootstrapper (`scripts/bootstrap_template.py`)**: One-command initialization script that customizes the template for your chosen programming language stack, installs git hooks, and seeds project metadata.
- 🚀 **GitHub CI & Governance (`.github/`)**: GitHub Actions workflow (`ci.yml`), GitHub Issue Forms (Feature, Bug, Tech Debt) with typed required fields and a chooser (`ISSUE_TEMPLATE/config.yml`) that disables blank issues, a commented `CODEOWNERS` stub, and a PR template enforcing task linking (`Closes #<issue>`).
- 🤝 **Community Health Stubs (`CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `.editorconfig`)**: Contributor Covenant v2.1, a Keep a Changelog seed, and a shared editor baseline (UTF-8, LF, final newline, trimmed trailing whitespace) that keeps editors from fighting the `trailing-whitespace` and `end-of-file-fixer` pre-commit hooks. Owner and contact placeholders are filled in by the bootstrapper.

---

## Quickstart

### 1. Initialize a New Repository from this Template

Use this repository as a template on GitHub, or clone it locally:

```bash
git clone https://github.com/your-org/ai-agent-template.git my-new-project
cd my-new-project
```

> [!NOTE]
> **Windows Users (`core.symlinks`)**: Ensure symlink creation is enabled during clone so `.claude/skills` is materialized as a true directory link rather than a text file:
>
> ```bash
> git clone -c core.symlinks=true https://github.com/your-org/ai-agent-template.git my-new-project
> ```

### 2. Run the Bootstrap Script

Run the language-agnostic bootstrapper to configure your project details and setup pre-commit quality gates:

```bash
# Interactive setup
python3 scripts/bootstrap_template.py

# Or specify your language stack, GitHub SEO metadata, and community health details directly
python3 scripts/bootstrap_template.py --name "my-awesome-app" --lang go --repo-desc "High-performance Go service built with AI Agent pair programming" --repo-topics "ai-agent,developer-tools,go" --repo-owner "my-org" --conduct-email "conduct@example.com"
```

The bootstrapper will:

1. Update project configuration files (`README.md`, `.agent-state.md`, `AGENTS.md`).
2. Generate language-specific `.gitignore` and `.pre-commit-config.yaml` rules.
3. Verify or create the `.claude/skills` auto-discovery symlink.
4. Seed the community health stubs (`CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/config.yml`) with your project name, and -- when `--repo-owner` / `--conduct-email` are supplied -- the GitHub owner and Code of Conduct contact. Any placeholder left unresolved is reported so you can edit it by hand.
5. Initialize local Git pre-commit hooks.
6. Inject initial documentation timestamps.
7. Configure GitHub Repository Description and SEO Topic Tags via `gh` CLI.

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
├── .gitignore                         # Language-agnostic ignore rules
├── .editorconfig                      # Shared editor baseline (UTF-8, LF, final newline)
├── .pre-commit-config.yaml            # Pre-commit quality gate configuration
├── .github/                           # CI workflows & GitHub templates
│   ├── copilot-instructions.md        # Discovery redirect to AGENTS.md (GitHub Copilot)
│   ├── CODEOWNERS                     # Commented ownership stub (see require_code_owner_review)
│   ├── PULL_REQUEST_TEMPLATE.md       # PR template with issue linking checks
│   ├── ISSUE_TEMPLATE/                # Structured GitHub Issue Forms
│   │   ├── bug_report.yml             # Bug form: description, repro, expected behaviour
│   │   ├── feature_request.yml        # Feature form: problem, solution, impact
│   │   ├── tech_debt.yml              # Tech debt form: canonical 10-category dropdown
│   │   └── config.yml                 # Issue chooser: blank issues off, contact links
│   └── workflows/ci.yml               # GitHub Actions CI workflow
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
│   └── release-management/            # Semantic versioning & release auditing
├── .agents/templates/                 # Tracked seed files copied into place by bootstrap
│   └── agent-state.md                 # Starter scratchpad seed for .agent-state.md
├── scripts/                           # Portable Python 3 helper utilities
│   ├── append_timestamps.py           # Injects markdown footer timestamps
│   ├── check_docs_review.py           # Validates doc freshness & review age
│   ├── bootstrap_template.py          # Project initializer script
│   └── gh_issue_sync.py               # GitHub issue & task plan helper
└── src/                               # Starter source directory placeholder
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
