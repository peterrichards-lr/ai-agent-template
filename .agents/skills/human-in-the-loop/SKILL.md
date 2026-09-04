---
name: human-in-the-loop
description: >-
  Enforces strict human verification gates before high-risk or irreversible operations.
  Load before deployments, database drops, secrets generation, or opening PRs.
---

# Skill: Human-in-the-Loop Verification

---

## Directives & Rules of Engagement

### 1. High-Risk Operation Gates
The agent MUST explicitly halt and request human approval before executing any of the following actions:
- Production deployments or infrastructure modification commands.
- Dropping, truncating, or purging database tables/volumes.
- Force pushing (`git push --force`) or overriding branch protection rules.
- Merging code into `main`/`master`.
- Creating or modifying repository branch protection / ruleset settings (see `docs/BRANCH_PROTECTION.md`) -- propose the change and wait for confirmation; don't apply it silently.
- Pushing a version tag or publishing a release (see `release-management/SKILL.md`) -- propose the version number and release notes, and wait for confirmation. Tags become immutable once `protect-version-tags.json` is applied, so a wrong one can't be cleaned up, only superseded.

Opening a Pull Request itself is not gated here -- it's cheap and fully reversible (just close it if it turns out to be wrong). Lumping it in with genuinely irreversible actions dilutes the seriousness of the ones that actually matter. The gate that matters is merging.

**Client-Side Harness Enforcement (`.claude/settings.json`)**:
Prose rules alone do not guarantee execution safety. This repository pairs these prose gates with client-side harness enforcement in `.claude/settings.json`, explicitly denying destructive commands (`rm -rf`, `git push --force`, `docker system prune`, `DROP DATABASE`, `gh repo delete`) and requiring interactive confirmation (`ask`) for high-risk actions (`gh pr merge`, `git tag`, `gh release create`).

### 2. Secret & Credentials Safety
- **No Plaintext Secrets**: The agent is FORBIDDEN from asking the user to provide plain text passwords, API keys, or private certificates in chat.
- **Local Generation**: Temporary development certificates or keys must be generated locally using standard non-interactive CLI tools.
- **Deletion Verification**: Before running `git commit`, temporary keys or certificates MUST be deleted (`rm <specific-path>` -- not `rm -rf`, which is a recursive-force flag meant for directories; using it as a reflex for single-file deletion is itself a risk if the path variable is ever wrong or empty) and verified via tool output.

### 3. Visual Modifications & Visual Diffing
Before finalizing UI component changes or layout edits, the agent MUST explicitly present the proposed modifications using visual markdown diff blocks or code slices and halt for visual approval.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-04* | *Last Reviewed: 2026-09-04*
