# Recommended Branch & Tag Protection (Optional, Strongly Recommended)

This template has extensive prose-based agent rules -- but prose alone doesn't
reliably bind agent behavior. That's not a hypothetical concern: a project
built on this exact pattern documented "every PR must close an issue" and had
it skipped on the next 5 PRs regardless, including by the agent that had just
written the rule, in the same session. The one thing that *did* reliably stop
unwanted behavior in that project was GitHub branch protection rejecting a
direct push outright, with no way to route around it. A template built to
harden AI-agent-assisted development should recommend the enforcement
mechanism proven to actually work, not just add more prose.

`.github/rulesets/` contains two ready-to-import [GitHub Repository
Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
(the modern replacement for classic branch protection rules) that turn
several of this template's conventions into real, unbypassable gates.

## `protect-main-branch.json`

- No direct pushes or force-pushes to the default branch -- all changes go
  through a PR.
- Requires this template's CI quality-gate job
  (`Code & Documentation Quality Verification`) and the Issue Link Check
  (`Verify PR references an issue`, see `.github/workflows/issue-link-check.yml`)
  to pass before merge.
- Requires at least 1 approving review. **Adjust this deliberately** if your
  team's workflow differs -- a solo developer importing this as-is cannot
  merge any PR because GitHub prohibits self-approval, and `bypass_actors: []`
  means admin override is not available either. A solo developer pairing
  closely with an agent should set `required_approving_review_count` to `0`
  before importing, trusting the plan-approval step in
  `.agents/skills/reflection-and-planning/SKILL.md` instead of a separate
  formal GitHub review click.
- Squash-merge only, linear history required.
- **No bypass actors** -- not even repo admins can override these rules. If a
  check is wrong, fix the check; don't route around it.

## `protect-version-tags.json`

- Version tags (`v*`) can't be deleted or moved once pushed. Only relevant
  once the project adopts semantic version tags/releases, but safe to import
  in advance regardless.

## Importing

These are provisioned via GitHub's Repository Rulesets API, not the legacy
branch-protection-rules UI. Importing requires a token with
**`Administration: Read and write`** on the repo -- this is normally a
one-time step a repo admin runs directly with their own authenticated `gh`
session, not something to fold into the agent's regular scoped PAT (see
`.agents/skills/github-workflow/SKILL.md` rule 5's PAT scope list, which
deliberately does not include Administration).

```bash
gh api --method POST repos/<owner>/<repo>/rulesets --input .github/rulesets/protect-main-branch.json
gh api --method POST repos/<owner>/<repo>/rulesets --input .github/rulesets/protect-version-tags.json
```

**Review the JSON before importing.** These are suggestions to adapt, not a
one-size-fits-all config to apply blindly:

- `required_status_checks[].context` values must exactly match your actual
  CI job names -- if you rename the `ci.yml` job or haven't added
  `issue-link-check.yml` yet, update or remove the corresponding entry first,
  or the required check will never be satisfiable and nothing will ever merge.
- `required_approving_review_count` should reflect a deliberate choice about
  your team's review model, not this file's default.
- `bypass_actors` is empty by default (nobody can bypass). Add an actor here
  only if you have a real, considered need for an emergency override path,
  and treat that as itself a high-risk change to make deliberately.
- **Path-Filtered CI Deadlock**: If downstream CI workflows adopt path filters
  (e.g. skipping heavy builds on docs-only changes), required status checks will
  stop reporting on filtered PRs, permanently deadlocking them in "Expected — Waiting
  for status to be reported". When downstream projects introduce heavy builds
  (such as language-specific compilation or long test suites, see Issue #42),
  they should adopt the **filter + same-named skip-job pattern**:
  a lightweight change-detection filter job gates execution, and both the primary
  heavy build job and a no-op skip job declare the identical display `name:`
  (e.g. `CI / Build & Test`). In successful filter runs, this allows the required
  status check context to report whether work was executed or skipped. Note that
  if the filter job itself fails, dependent jobs are skipped by GitHub Actions
  unless explicit failure handling is configured.

An agent proposing this import to you, or modifying an existing ruleset, is a
high-risk operation under `.agents/skills/human-in-the-loop/SKILL.md` -- it
should describe the change and wait for you to confirm or run it yourself,
not apply it silently.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-04* | *Last Reviewed: 2026-09-04*
