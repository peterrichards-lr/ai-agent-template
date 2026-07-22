# AI Agent Development Quickstart Template

A production-ready, language-agnostic template repository designed to accelerate **AI Agent-Assisted Software Development**.

Whether you are building in **Go**, **Python**, **Rust**, **Java**, **TypeScript / Node.js**, **C++**, or **Liferay**, this repository provides the structural foundation, active agent constraints, modular skill rules, state management, and automated quality gates required for seamless pair programming with AI agents (such as Antigravity, Claude, Gemini, ChatGPT, etc.).

---

## Key Features

- 🧠 **Context-Optimized Agent Routing (`AGENTS.md`)**: Decouples agent rules into domain-specific skill files (`.agents/skills/`), preventing prompt bloat and context token exhaustion.
- 📌 **Persistent State Engine (`GEMINI.md`)**: Maintains continuity across chat sessions by tracking project status, active goals, roadmap items, and rules of engagement.
- 🛡️ **Language-Agnostic Quality Gates (`.pre-commit-config.yaml`)**: Out-of-the-box pre-commit configuration supporting secret scanning (`detect-secrets`, `gitleaks`), markdown link validation, document review policies, and modular linting for Go, Python, Rust, Java, and Node.js.
- ⏱️ **Automated Documentation Hygiene**: Zero-dependency Python 3 tools (`append_timestamps.py` and `check_docs_review.py`) to enforce timestamp footers (`*Last Updated* | *Last Reviewed*`) and prevent documentation decay.
- ⚙️ **Project Bootstrapper (`scripts/bootstrap_template.py`)**: One-command initialization script that customizes the template for your chosen programming language stack, installs git hooks, and seeds project metadata.
- 🚀 **GitHub CI & Governance (`.github/`)**: GitHub Actions workflow (`ci.yml`), issue templates (Feature, Bug, Tech Debt), and a PR template enforcing task linking (`Closes #<issue>`).

---

## Quickstart

### 1. Initialize a New Repository from this Template

Use this repository as a template on GitHub, or clone it locally:

```bash
git clone https://github.com/your-org/ai-agent-template.git my-new-project
cd my-new-project
```

### 2. Run the Bootstrap Script

Run the language-agnostic bootstrapper to configure your project details and setup pre-commit quality gates:

```bash
# Interactive setup
python3 scripts/bootstrap_template.py

# Or specify your language stack directly (e.g., go, python, rust, java, node, generic)
python3 scripts/bootstrap_template.py --name "my-awesome-app" --lang go
```

The bootstrapper will:

1. Update project configuration files (`README.md`, `GEMINI.md`, `AGENTS.md`).
2. Generate language-specific `.gitignore` and `.pre-commit-config.yaml` rules.
3. Initialize local Git pre-commit hooks.
4. Inject initial documentation timestamps.

---

## Repository Structure

```text
.
├── AGENTS.md                          # Master routing index for AI agent skills
├── GEMINI.md                          # Persistent state tracking document
├── CONTRIBUTING.md                    # Guidelines for human & AI agent contributors
├── README.md                          # This file
├── LICENSE                            # MIT License
├── .gitignore                         # Language-agnostic ignore rules
├── .pre-commit-config.yaml            # Pre-commit quality gate configuration
├── .github/                           # CI workflows & GitHub templates
│   ├── PULL_REQUEST_TEMPLATE.md       # PR template with issue linking checks
│   ├── ISSUE_TEMPLATE/                # Task, Bug, and Tech Debt templates
│   └── workflows/ci.yml               # GitHub Actions CI workflow
├── .agents/skills/                    # Modular skill instructions for AI agents
│   ├── reflection-and-planning/       # Logic-first planning & approval loops
│   ├── human-in-the-loop/             # Safety verification gates for risky operations
│   ├── coding-standards/              # DRY code, self-documenting code & error safety
│   ├── unit-testing/                  # TDD & non-interactive test rules
│   ├── documentation/                 # Timestamp & doc maintenance rules
│   ├── github-workflow/               # Issue sync, PR constraints & CI cleanup
│   ├── tool-use-react/                # ReAct reasoning & CLI command boundaries
│   └── multi-agent-orchestration/     # Subagent delegation directives
├── scripts/                           # Portable Python 3 helper utilities
│   ├── append_timestamps.py           # Injects markdown footer timestamps
│   ├── check_docs_review.py           # Validates doc freshness & review age
│   ├── bootstrap_template.py          # Project initializer script
│   └── gh_issue_sync.py               # GitHub issue & task plan helper
└── src/                               # Starter source directory placeholder
```

---

## AI Agent Workflow & Interaction Model

When interacting with an AI coding assistant in this repository, the agent will automatically follow the **Rules of Engagement** specified in `AGENTS.md` and `GEMINI.md`:

1. **State Persistence**: Before making structural changes, the agent updates `GEMINI.md` to persist current context.
2. **Context-Driven Skill Activation**: The agent loads only the relevant `.agents/skills/<skill>/SKILL.md` file required for the current task.
3. **Logic-First Planning**: For complex changes, the agent presents an implementation plan before modifying files.
4. **Documentation Sync**: After writing code, the agent runs `scripts/append_timestamps.py` and `scripts/check_docs_review.py` to maintain documentation hygiene.
5. **Quality Verification**: All changes are validated using non-interactive test commands before marking a task complete.

---

## License

This template is open source and available under the [MIT License](LICENSE).

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
