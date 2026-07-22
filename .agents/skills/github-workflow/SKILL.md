# Skill: GitHub Workflow & Issue Synchronization

**Trigger Condition**: Load this skill when starting tasks, managing GitHub issues, creating Pull Requests, or dealing with CI runner failures.

---

## Directives & Rules of Engagement

### 1. Primary Tool Usage (`gh` CLI)
All GitHub interactions MUST use the GitHub CLI (`gh`). Custom Python scripts using raw REST APIs or external libraries for GitHub API access are forbidden.

### 2. Issue Synchronization & Task Linking
- Every Pull Request MUST close a parent GitHub issue. In the PR body, include `Closes #<issue-number>`.
- Before creating a PR, verify branch status against main (`git fetch origin main && git log HEAD..origin/main --oneline`).

### 3. CI Failure Analysis & Cleanup
- If a GitHub Actions CI job fails, view logs via `gh run list` and `gh run view <run-id> --log`.
- Fix the underlying cause and push a verified fix.
- Once a fix is verified green, delete the historical record of failed runs (`gh run delete <run-id>`) to keep the build history clean.

### 4. Technical Debt Issue Creation
When encountering any of the 10 catalogued tech debt categories (Code Smells, Duplication, Over-complexity, Fragile Coupling, Missing Safety Guards, Missing Tests, Security Hygiene, Deprecated Patterns, Config Drift, Documentation Debt), immediately create a GitHub issue:

```bash
gh issue create --title "Tech Debt: [Title]" --body "[Details, File Path, Proposed Fix]" --label "tech-debt"
```

### 5. Fine-Grained PAT & Authentication Setup

To authenticate `gh` CLI commands non-interactively without storing plaintext secrets in repository files:

#### Required Fine-Grained PAT Scopes (Least Privilege)
Create a Fine-Grained Personal Access Token (PAT) scoped strictly to target repositories with the following permissions:
- **`Actions: Read and write`**: Required for listing runs (`gh run list`), viewing logs (`gh run view`), and deleting historical failed runs (`gh run delete`).
- **`Workflows: Read and write`**: Required if the agent modifies or pushes changes to workflow YAML files under `.github/workflows/*.yml`.
- **`Issues: Read and write`**: Required for creating/syncing issues (`gh issue create`) and tech-debt logging.
- **`Pull requests: Read and write`**: Required for opening PRs and linking issue closures (`Closes #<issue>`).
- **`Contents: Read and write`**: Required for branching, committing, and pushing code.

#### Organization Owner Approval Gotcha
For organization-owned repositories, Fine-Grained PATs require explicit **Organization Owner approval** in Organization Settings before access is granted. Token requests will return 403 Forbidden errors until approved.

#### Secure Secret Storage Guidance
Expose the token via `export GH_TOKEN="github_pat_..."` inside non-tracked shell profiles (`~/.zshrc`, `~/.bashrc`), password managers, or CI environment secrets. **NEVER** commit tokens into `.env`, `Makefile`, or tracked codebase files.

#### Expiration & Token Rotation
Expired tokens trigger `401 Unauthorized` errors on `gh` commands. Set calendar reminders to rotate 30/90-day tokens proactively.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
