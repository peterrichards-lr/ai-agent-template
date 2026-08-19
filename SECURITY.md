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

## Security Best Practices for AI Agents

All AI assistants pairing in this repository MUST follow the security rules in [`AGENTS.md`](./AGENTS.md) and [`.agents/skills/coding-standards/SKILL.md`](./.agents/skills/coding-standards/SKILL.md):

- **No Hardcoded Credentials**: Pass secrets via environment variables or secret managers.
- **Least-Privilege Scopes**: Fine-grained PATs must use minimal repository permissions (`Contents`, `Issues`, `Pull Requests`).
- **Dependencies Verification**: Validate third-party libraries and avoid untrusted dependencies.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-08-19* | *Last Reviewed: 2026-08-19*
