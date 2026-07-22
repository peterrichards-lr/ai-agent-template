# Skill: Human-in-the-Loop Verification

**Trigger Condition**: Load this skill when performing destructive actions, production deployments, database migrations/drops, credentials handling, or submitting Pull Requests.

---

## Directives & Rules of Engagement

### 1. High-Risk Operation Gates
The agent MUST explicitly halt and request human approval before executing any of the following actions:
- Production deployments or infrastructure modification commands.
- Dropping, truncating, or purging database tables/volumes.
- Force pushing (`git push --force`) or overriding branch protection rules.
- Opening a Pull Request or merging code into `main`/`master`.

### 2. Secret & Credentials Safety
- **No Plaintext Secrets**: The agent is FORBIDDEN from asking the user to provide plain text passwords, API keys, or private certificates in chat.
- **Local Generation**: Temporary development certificates or keys must be generated locally using standard non-interactive CLI tools.
- **Deletion Verification**: Before running `git commit`, temporary keys or certificates MUST be deleted (`rm -rf`) and verified via tool output.

### 3. Visual Modifications & Visual Diffing
Before finalizing UI component changes or layout edits, the agent MUST explicitly present the proposed modifications using visual markdown diff blocks or code slices and halt for visual approval.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
