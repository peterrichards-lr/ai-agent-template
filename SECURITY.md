# Security Policy & Secret Hygiene Guidelines

`ai-agent-template` is designed for secure AI Agent-assisted software development. This policy outlines vulnerability disclosure procedures, secret scanning quality gates, and automated security practices.

---

## Supported Versions

Only the latest `main` branch and tagged release versions receive security updates and active dependency scanning.

| Version / Branch | Supported | Notes |
| :--- | :--- | :--- |
| `main` | YES | Active development branch |
| Tagged Releases (`v1.x`) | YES | Supported release versions |
| Legacy Branches | NO | Upgrade to latest release |

---

## Reporting a Vulnerability

If you discover a security vulnerability, hardcoded secret, or security flaw within this template or projects generated from it:

1. **Do NOT open a public GitHub issue.**
2. Send a private report detailing the vulnerability, impact, and reproduction steps to the repository maintainers or via GitHub Private Vulnerability Reporting (if enabled on the repository settings).
3. The security team will acknowledge receipt within **48 hours** and provide periodic updates on remediation progress.

---

## Secret Scanning & Prevention Gates

This repository enforces multi-layered pre-commit secret scanning to prevent accidental exposure of API keys, tokens, or credentials:

1. **Local Pre-commit Hook**: Configured with `detect-secrets` and `gitleaks` in `.pre-commit-config.yaml`.
2. **`gh` CLI Authentication**: Requires Fine-Grained Personal Access Tokens (PATs) passed strictly via environment variables (`GH_TOKEN`), never hardcoded in files.
3. **Automated Dependency Audit**: Dependencies are monitored via `.github/dependabot.yml` and pre-commit version hooks.

---

## Static Analysis & Dependency Review

Secret scanning only proves no credential was committed; it says nothing about the code itself. [`.github/workflows/security-scan.yml`](./.github/workflows/security-scan.yml) adds two scanners on every push and pull request:

| Job | Tool | What it catches |
| :--- | :--- | :--- |
| `Semgrep SAST (non-blocking)` | Semgrep OSS (`p/ci`, `p/secrets`, plus the language pack chosen by `scripts/bootstrap_template.py`) | Insecure code patterns, and this project's own rules from [`.semgrep.yaml`](./.semgrep.yaml) |
| `Dependency Review (non-blocking)` | [`actions/dependency-review-action`](https://github.com/actions/dependency-review-action) | Newly introduced dependencies with known vulnerabilities |

Both jobs are **non-blocking by design**: they set `continue-on-error: true` and are deliberately absent from the required status checks in [`.github/rulesets/protect-main-branch.json`](./.github/rulesets/protect-main-branch.json). A newly bootstrapped project must not fail CI on day one because of a finding in a third-party transitive dependency. Once findings are triaged to zero, promote a job by removing its `continue-on-error` and adding its name to the ruleset in the same change.

Semgrep, not CodeQL, is the shipped default: it runs entirely inside the job (so it reports findings in a private repository without GitHub Advanced Security), covers every stack the template bootstraps, and is the only one of the two that supports the project-specific rules in `.semgrep.yaml`. CodeQL remains complementary for public or GHAS-enabled repositories -- enable it via *Settings > Code security > CodeQL analysis > Default setup*, or uncomment the job stub at the foot of the workflow.

Uploading Semgrep results to the **Security** tab, and dependency review itself, both require a public repository or GitHub Advanced Security. Without it the findings are still printed in the workflow job log.

---

## Security Best Practices for AI Agents

All AI assistants pairing in this repository MUST follow the security rules in [`AGENTS.md`](./AGENTS.md) and [`.agents/skills/coding-standards/SKILL.md`](./.agents/skills/coding-standards/SKILL.md):

- **No Hardcoded Credentials**: Pass secrets via environment variables or secret managers.
- **Least-Privilege Scopes**: Fine-grained PATs must use minimal repository permissions (`Contents`, `Issues`, `Pull Requests`).
- **Dependencies Verification**: Validate third-party libraries and avoid untrusted dependencies.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
