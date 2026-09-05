# Contributing Guidelines

Thank you for contributing to this project! Whether you are a human developer or an AI agent assistant, please follow these guidelines to ensure code quality, documentation integrity, and smooth collaboration.

---

## 1. Rules of Engagement for AI Coding Agents

When working on this repository, AI agents MUST follow the operational directives defined in:
1. **[AGENTS.md](AGENTS.md)**: Routing index for modular skills and universal engagement rules (canonical single source of truth).
2. **`.agent-state.md`**: In-flight task scratchpad state, active objectives, and session context across AI provider switches (gitignored).
3. **`.agents/skills/`**: Specific task instructions (`reflection-and-planning`, `unit-testing`, `coding-standards`, `github-workflow`, etc.).
4. **[docs/BRANCH_PROTECTION.md](docs/BRANCH_PROTECTION.md)**: Recommended repository rulesets that turn several of the above conventions into real, CI/platform-enforced gates rather than prose alone.

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

### Commit Attribution

Configure a `git config user.email` that GitHub can attribute to your account **before** you commit. A repository ruleset or org policy may require an extra approving review for unattributed changes, and a solo maintainer cannot satisfy that -- leaving history rewriting and force-pushing as the only escape from an already-pushed commit.

The `check-commit-attribution` pre-commit hook (`scripts/check_commit_attribution.py`) catches this while the fix is still a one-liner. It passes when your email is a GitHub noreply address:

```bash
git config user.email "<ID>+<username>@users.noreply.github.com"
```

(Your noreply address is shown at GitHub -> Settings -> Emails -> "Keep my email addresses private".)

> [!NOTE]
> **The check is a heuristic, not a verdict on your email.** It recognises `@users.noreply.github.com` addresses and an explicit allowlist; it cannot see which addresses are verified on your GitHub account. An address on a verified custom domain attributes perfectly well and will still fail the check. If yours is already verified on GitHub, allowlist it rather than changing it:
>
> ```bash
> git config --add user.attributableEmails "you@your-verified-domain.example"
> ```
>
> The key is multi-valued (`git config --get-all user.attributableEmails`), so repeat the command to allowlist several addresses.

See [docs/BRANCH_PROTECTION.md](docs/BRANCH_PROTECTION.md) for the ruleset side of this trap.

---

## 3. Pull Request Protocol

Before opening a Pull Request, run the full local quality gate:

```bash
make verify
```

`make verify` is `lint` + `test` + `docs`, and it is **exactly** what `.github/workflows/ci.yml`
runs -- the workflow invokes these targets rather than restating the commands, so the two cannot
drift. CI splits the chain across two jobs: `Code & Documentation Quality Verification` always
runs `lint-tooling` and `docs`, while `Build & Test` runs `lint-lang` and `test` behind a paths
filter that skips it for documentation-only changes. The union is `make verify`, with nothing
dropped and nothing run twice. "Did I break CI?" is therefore still one local command. The
individual targets (`make lint`, `make test`, `make docs`) are available when you want to run
just one; `make help` lists them all.

Each ecosystem's real test command lives in the `Makefile`'s language profile block, stated once
and filled in by `scripts/bootstrap_template.py --lang <stack>`. Do not restate it here, in
`AGENTS.md` or in a skill file: that is how the copies drift apart.

Then:
1. Ensure your PR description references the parent issue (e.g., `Closes #123`).
2. Push with `make push MESSAGE="feat(scope): what changed"`. It refuses a no-op push, refuses to
   commit while tracked files are still unstaged, rejects a flag-shaped commit message, and runs
   the pre-commit gate rather than bypassing it. `--force-with-lease` is the only sanctioned force
   form (`make push PUSH_ARGS=--force-with-lease`); bare `--force` is denied client-side by
   `.claude/settings.json`.

> [!NOTE]
> `make` is not installed by default on Windows. See the note in [README.md](README.md#windows-notes).

---

## 4. Documentation & Timestamp Hygiene

All Markdown (`.md`) files in this repository MUST include a standardized footer tracking updates and reviews:

```markdown
<!-- markdownlint-disable MD049 -->
---
*Last Updated: YYYY-MM-DD* | *Last Reviewed: YYYY-MM-DD*
```

Run `python3 scripts/check_docs_review.py` before submitting changes to verify compliance.

---

## 5. AI Agent Authentication & Fine-Grained PAT Configuration

When configuring non-interactive authentication for AI agent pair programmers, follow the **Principle of Least Privilege**:

### Creating a Fine-Grained Personal Access Token (PAT)
In GitHub Settings -> Developer Settings -> Fine-grained Tokens:
- **Repository Access**: *Only select repositories* (target repo only).
- **Permissions**:
  - `Actions: Read and write` (Required for `gh run list`, `gh run view`, and `gh run delete` CI failure cleanup).
  - `Workflows: Read and write` (Required if the agent edits or pushes files in `.github/workflows/*.yml`).
  - `Issues: Read and write` (Required for creating/updating issues and running `gh_issue_sync.py`).
  - `Pull requests: Read and write` (Required for opening PRs with `Closes #<issue>`).
  - `Contents: Read and write` (Required for branching, committing, and pushing code).

> [!IMPORTANT]
> **Organization Owner Approval**: For organization-owned repositories, Fine-Grained PATs require explicit Organization Owner approval in Organization Settings before access is active.

### Secure Token Storage
Expose the token to `gh` CLI via `export GH_TOKEN="github_pat_..."` inside non-tracked user shell profiles (`~/.zshrc`, `~/.bashrc`), password managers, or CI environment secrets. **NEVER** commit tokens into `.env`, `Makefile`, or tracked codebase files.

### Token Expiration & Rotation
Expired PATs trigger `401 Unauthorized` errors on `gh` commands. Set calendar reminders to rotate 30/90-day tokens proactively.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
