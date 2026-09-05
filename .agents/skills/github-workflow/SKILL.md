---
name: github-workflow
description: >-
  Standardizes GitHub CLI usage, mandatory issue linking (Closes #<issue>), the PR review feedback loop, repository SEO, and CI run cleanup.
  Load when managing issues, opening PRs, responding to review comments, or handling CI failures.
---

# Skill: GitHub Workflow & Issue Synchronization

---

## Directives & Rules of Engagement

### 1. Primary Tool Usage (`gh` CLI)
All GitHub interactions MUST use the GitHub CLI (`gh`). Custom Python scripts using raw REST APIs or external libraries for GitHub API access are forbidden.

### 2. Issue Synchronization & Task Linking
- Every Pull Request MUST close a parent GitHub issue. In the PR body, include `Closes #<issue-number>` strictly inside the `## Linked Issue` section.
- Multiple closing references are permitted within `## Linked Issue` (e.g. `Closes #30\nCloses #43`).
- **Positional Anchoring & Negation Trap**: Closing keywords (`closes`, `fixes`, `resolves`) followed by `#<number>` are forbidden in the PR title and outside the `## Linked Issue` section. GitHub's parser ignores English negations (e.g. `does not close #123`, `not fixing #123`), which causes premature, silent issue closure on merge. For non-closing references, use phrases without closing keywords: `part of #123`, `see #123`, `related to #123`, `addresses #123`, or plain `#123`.
- Before creating a PR, verify branch status against main (`git fetch origin main && git log HEAD..origin/main --oneline`).
- Once an implementation plan for that issue is approved (see `reflection-and-planning/SKILL.md` Rule 3), post a concise summary of it as a comment on the issue before starting implementation -- keeps a readable record of what was planned independent of the agent's chat session.

**This is CI-enforced, not just documented here.** The "Issue Link Check"
workflow (`.github/workflows/issue-link-check.yml`) executes `scripts/check_closing_refs.py`,
failing any PR with stray closing keywords or lacking a valid closing reference in `## Linked Issue`
(unless the PR carries the `no-issue-needed` label -- an intentional escape hatch for genuinely
trivial changes).
Prose-only versions of this rule don't reliably get followed -- a sibling
project documented the exact same requirement and then had it skipped on the
next 5 PRs regardless, including by the agent that had just written the
rule. File the issue *before* running `gh pr create`; a CI failure after the
fact just means going back to create one anyway. Once this check has proven
out, add it to the repo's required status checks in branch protection
settings -- that step can't be done from a workflow file alone.

### 3. PR Review & CI Feedback Loop

Opening the PR is the middle of the task, not the end of it. Retrieving the feedback on an open PR takes **two calls, not one** -- they return different data, and neither is a substitute for the other:

```bash
# Review summaries, conversation comments, and CI status.
gh pr view <number> --json reviews,comments,statusCheckRollup

# Inline review threads -- the comments anchored to a file and line.
gh api 'repos/{owner}/{repo}/pulls/<number>/comments'
```

> [!IMPORTANT]
> **Do not "simplify" this back to a single command.** `gh pr view` has
> no field for inline review comments. Its `comments` field is the PR conversation
> timeline and `reviews` is review *summaries* (author, state, top-level body); the
> complete set of review-related `--json` fields is `comments`, `latestReviews`,
> `reviewDecision`, `reviewRequests`, `reviews`, and not one of them carries a `path`
> or a `line`. The `gh api` call is the only source of the `path`, `line` and `body`
> that the "map each comment to the specific file and line" instruction below operates
> on. An agent running just the first command sees a review summary, finds nothing
> anchored to a file, and reports the loop closed while inline comments sit unanswered.
> Pass `<number>` explicitly in both: bare `gh pr view` resolves the PR from the currently checked-out branch, which is not where you are when reviewing someone else's PR.

- **Retrieve feedback directly.** Never ask the user to paste review comments, check names, or CI logs into the chat. The agent has the same `gh` access the human does; asking them to relay it wastes their turn and loses the file/line context. `statusCheckRollup` in the first query is the CI status, so this pair covers both "what did the reviewer say" and "is the build green" -- reach for `gh run list` only to resolve a failing check into a run id.
- **Close the loop on every comment.** Map each comment to the specific file and line it concerns (`path` and `line` from the `gh api` response), state the plan for addressing it, apply the fix, then re-run both queries above and report back which comments were addressed and how. **A review comment left neither actioned nor answered is an open thread, not a resolved one** -- it becomes something the PR author has to chase.
- **Answering counts; silence does not.** Disagreeing with a comment, deferring it to a follow-up issue, or explaining why it does not apply are all legitimate closures -- provided the reasoning is posted on the PR (`gh pr comment`), not just narrated in chat. Only a comment nobody replied to and nobody actioned is unresolved.
- **CI failure analysis and cleanup.** When `statusCheckRollup` reports a failing check, pull the logs (`gh run view <run-id> --log`), fix the underlying cause, and push a verified fix -- never re-run a job hoping for a different result. Once the fix is verified green, delete the historical record of failed runs (`gh run delete <run-id>`) to keep build history clean.

**Interaction with `human-in-the-loop/SKILL.md`**: pushing fixes in response to review is routine and needs no approval gate -- it is cheap and reversible, exactly like opening the PR was. Resolving a reviewer's thread on their behalf is not routine: marking a conversation resolved is the reviewer's own signal that they are satisfied with the answer. Push the fix, reply on the thread, and leave it to the reviewer to close.

### 4. Technical Debt Issue Creation
Tech debt you notice but don't fix as part of the current task must still be tracked -- untracked debt is debt that never gets paid down. This is the single canonical place tech debt is tracked in this template: as a GitHub issue labeled `tech-debt`. Do not also maintain a separate registry elsewhere (`GEMINI.md` points back here rather than keeping its own list, for exactly this reason).

The 10 catalogued categories: Code Smells, Duplication, Over-complexity, Fragile Coupling, Missing Safety Guards, Missing Tests, Security Hygiene, Deprecated Patterns, Config Drift, Documentation Debt.

Apply this without derailing the task you're actually doing:
- **Don't halt mid-task.** Keep working; log tech debt at a natural checkpoint (before opening your PR is fine) rather than interrupting the current edit the moment you spot something.
- **Dedup first.** Before filing, check for an existing open issue covering the same thing: `gh issue list --label "tech-debt" --search "<keyword>"`. If one exists, comment or `+1` on it instead of creating a duplicate.
- **Batch related findings into one issue.** If a single pass surfaces several instances of the same category (e.g. three duplicated helper functions), file one issue describing the pattern with all instances listed, not one issue per instance.
- **Bar for filing.** File it if it's a real, specific problem you can point at -- not a vague "this area could be cleaner." If you can't say what a future agent should do with it, it's not ready to file yet.

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

### 6. Repository SEO Optimization (Description & Topics Mandate)

To ensure high visibility, search discoverability, and SEO positioning on GitHub:
- Every repository generated from or using this template MUST have a concise, keyword-rich **Repository Description** and appropriate **Topics (Tags)** set.
- Minimum required topic tags: `ai-agent`, `developer-tools`, and the primary language/stack identifier (e.g., `python`, `go`, `rust`, etc.).
- Set or update repository SEO metadata using the `gh` CLI:

  ```bash
  gh repo edit --description "<concise keyword-rich summary>" --add-topic "ai-agent,developer-tools,<language>"
  ```

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
