# Project Persistent State & Planning (`GEMINI.md`)

This document maintains persistent state across AI agent sessions. It records project goals, architectural constraints, completed tasks, active work state, technical debt, and roadmap priorities.

> [!NOTE]
> **Agent Directive**: AI agents MUST inspect and update this file before beginning work and after completing major milestones to ensure seamless state preservation.

---

## 1. Project Goal & Overview
- **Goal**: Core development for quickstart-demo.
- **Target Stack**: Go
- **Architecture Overview**: [Brief description of key components, packages, or services]

---

## 2. Active Constraints & Security Directives

### Security & Secrets Management
- **No Plaintext Credentials**: *Active Constraint*: Never commit or hardcode private keys, API tokens, certificates, or passphrases. Use environment variables, keyrings, or standard secret vaults.
- **Temporary File Cleanup**: *Active Constraint*: Always delete temporary key files, certificates, or scratch artifacts before committing code.

### Workflow & Quality Enforcement
- **Multi-File Edits**: *Active Constraint*: Before executing multi-file edits, present an implementation plan and obtain approval.
- **Atomic Changes**: *Active Constraint*: Execute changes in discrete, verifiable units.
- **Predictive Failure Analysis**: *Active Constraint*: Append a "Failure Analysis" section to non-trivial logic edits detailing two edge cases and how the code handles them.
- **Non-Interactive Execution**: *Active Constraint*: Append `-y` or `--non-interactive` flags to all CLI tooling invocations.

---

## 3. Active Work State & Task Checklist

- [x] Template repository initialization (`AGENTS.md`, `README.md`, `GEMINI.md`).
- [ ] Bootstrap new project using `scripts/bootstrap_template.py`.
- [ ] Define core domain model and project modules in `src/`.
- [ ] Implement unit test suite baseline in `tests/` or equivalent.
- [ ] Setup GitHub Action CI quality workflow.

---

## 4. Technical Debt Registry

| Debt ID | Category | Location | Description | Proposed Remediation | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| *None recorded yet* | - | - | - | - | - |

---

## 5. Feature Roadmap & Prioritization

| Feature / Topic | Description | LOE | Business Value | Priority | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Core Engine Baseline** | Initial application skeleton and primary logic. | Medium | High | **High** | Planned |
| **Test Suite Expansion** | Automated unit and integration test coverage. | Small | High | **High** | Planned |
| **CI/CD Quality Gate** | Automated linting, test verification, and security scanning on PRs. | Small | Medium | **Medium** | Planned |

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
