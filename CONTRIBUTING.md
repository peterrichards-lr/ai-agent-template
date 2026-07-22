# Contributing Guidelines

Thank you for contributing to this project! Whether you are a human developer or an AI agent assistant, please follow these guidelines to ensure code quality, documentation integrity, and smooth collaboration.

---

## 1. Rules of Engagement for AI Coding Agents

When working on this repository, AI agents MUST follow the operational directives defined in:
1. **[AGENTS.md](AGENTS.md)**: Routing index for modular skills and universal engagement rules.
2. **[GEMINI.md](GEMINI.md)**: Persistent state, active roadmap, and project constraints.
3. **`.agents/skills/`**: Specific task instructions (`reflection-and-planning`, `unit-testing`, `coding-standards`, etc.).

---

## 2. Git Branching & Commit Conventions

### Branch Naming Strategy
All work must be performed on dedicated topic branches created from `main` (or `master`):
- `feature/<issue-number>-short-description` (e.g. `feature/42-auth-handler`)
- `bugfix/<issue-number>-short-description` (e.g. `bugfix/108-null-pointer-fix`)
- `refactor/<issue-number>-short-description` (e.g. `refactor/55-modularize-router`)
- `docs/<issue-number>-short-description` (e.g. `docs/12-update-readme`)

### Commit Messages
We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
- `feat(scope): add user authentication endpoint`
- `fix(scope): handle null value gracefully in user lookup`
- `docs(readme): add setup instructions for Go and Python`
- `test(auth): add unit test coverage for token expiration`
- `refactor(db): extract connection pool logic into helper`

> [!CAUTION]
> **No Bypass Rule**: Never use `git commit --no-verify`. Pre-commit hooks are enforced quality gates. If a specific tool fails due to local missing tools, use targeted skip flags (e.g. `SKIP=detect-secrets git commit`).

---

## 3. Pull Request Protocol

Before opening a Pull Request:
1. Ensure all unit tests pass cleanly: `pytest`, `go test ./...`, `cargo test`, `npm test`, or equivalent.
2. Run pre-commit checks locally: `pre-commit run --all-files`.
3. Update documentation and inject timestamp footers via `python3 scripts/append_timestamps.py`.
4. Ensure your PR description references the parent issue (e.g., `Closes #123`).

---

## 4. Documentation & Timestamp Hygiene

All Markdown (`.md`) files in this repository MUST include a standardized footer tracking updates and reviews:

```markdown
<!-- markdownlint-disable MD049 -->
---
*Last Updated: YYYY-MM-DD* | *Last Reviewed: YYYY-MM-DD*
```

Run `python3 scripts/check_docs_review.py` before submitting changes to verify compliance.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
