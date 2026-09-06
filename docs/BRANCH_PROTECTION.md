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
  (`Code & Documentation Quality Verification`), its language build job
  (`Build & Test` -- see the note below before importing), the Issue Link Check
  (`Verify PR references an issue`, see `.github/workflows/issue-link-check.yml`),
  and the Scope Sprawl Gate (`Verify PR scope sprawl guardrail`, see
  `.github/workflows/pr-scope-check.yml`) to pass before merge.
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
- **Unattributed-changes approval** is the same solo-maintainer trap wearing a
  different hat, and it's the specific tightening to think twice about. The
  `pull_request` rule accepts a
  `require_extra_approval_for_unattributed_changes` parameter, which demands an
  extra approving review for any commit whose author email GitHub can't map to a
  verified account. **Neither ruleset in `.github/rulesets/` sets it** -- so if
  you hit this on a repo built from this template, it came from an org-level
  policy or from a rule someone added later, not from importing these files. Do
  not add it without an answer to "who approves?": a lone maintainer can't
  self-approve, `bypass_actors: []` removes the admin override, and the only
  escape from an already-pushed commit is rewriting history and force-pushing --
  itself a high-risk operation under
  `.agents/skills/human-in-the-loop/SKILL.md`. Whether or not you enable the
  rule, `scripts/check_commit_attribution.py` (wired into
  `.pre-commit-config.yaml`) catches an unattributable author email *before* the
  commit exists, when the fix is one `git config` line. See
  [CONTRIBUTING.md](../CONTRIBUTING.md) for configuring it.
- `bypass_actors` is empty by default (nobody can bypass). Add an actor here
  only if you have a real, considered need for an emergency override path,
  and treat that as itself a high-risk change to make deliberately.
- **Path-Filtered CI Deadlock**: A path filter that skips a heavy build on a
  documentation-only change also stops the filtered job reporting its status,
  so a pull request requiring that context deadlocks in "Expected — Waiting for
  status to be reported". `.github/workflows/ci.yml` -- installed from
  `.agents/templates/ci/<lang>.yml` by
  `scripts/bootstrap_template.py --lang <stack>` -- ships the **filter +
  same-named skip-job pattern** that avoids it. Four properties make it work,
  and each of them has a specific failure behind it:
  - **The doc checks are never filtered.** `Code & Documentation Quality
    Verification` carries no `needs:` and no `if:`, so it runs on every push and
    pull request. An earlier attempt filtered the whole workflow and was reverted
    before merge, because that workflow was *entirely* documentation validation:
    excluding `**/*.md` disabled markdownlint, the provider-redirect check, the
    doc-footer guard and the skill-routing drift test for exactly the pull
    requests they exist to catch. See Issues #42 and #44.
  - **Only the heavy build sits behind the filter**, and `build-and-test` and
    `build-and-test-skip` declare the identical `name: Build & Test`, so exactly
    one of the pair runs and the context is reported either way. The filter's
    documentation exclusions themselves ship **commented out**: enable them only
    once you have checked that nothing behind the filter reads the paths you are
    excluding. This template's own test suite reads its documentation, which is
    why they are inert here.
  - **A broken filter fails loudly.** The skip job's condition is
    `always() && needs.filter.outputs.code != 'true'`. The `always()` is
    load-bearing: if the filter job itself fails, GitHub skips its dependent
    jobs whatever their `if:` says, so without it a failed filter would skip
    *both* jobs, nothing would report the context, and the deadlock would merely
    have moved to the filter job. With it, the skip job runs, sees
    `needs.filter.result != 'success'` and exits non-zero -- a red check with a
    readable reason instead of a silent absence.
  - **No `strategy.matrix` on a job supplying a fixed-name context.** GitHub
    reports a matrix job as `Build & Test (some-value)` and never the bare name,
    so a ruleset requiring the bare name would wait forever, and
    `tests/test_template_scripts.py::test_ruleset_status_checks_match_workflow_jobs`
    would fail it as unmatched. Keep a fixed-name aggregating job as the context
    and put the matrix in a job beneath it.
- **`Build & Test` is a required status check, and this is the entry to think
  twice about.** It is listed in `required_status_checks` deliberately: CI whose
  failure nobody has to act on is decoration, and a template that ships a build
  job it does not enforce has repeated the problem it set out to fix. The cost
  is that a repository which cannot build yet cannot merge anything --
  `--lang generic` makes `make test` exit non-zero by design, and the Node and
  Java profiles cannot install dependencies until a lockfile or `pom.xml` is
  committed. **If your project is not yet building, delete the
  `{ "context": "Build & Test" }` line before importing this ruleset** and add
  it back once the job is green. That is a one-line edit made once; the
  alternative -- shipping the check advisory -- is a permanently weaker gate for
  every adopter who never gets round to promoting it.

An agent proposing this import to you, or modifying an existing ruleset, is a
high-risk operation under `.agents/skills/human-in-the-loop/SKILL.md` -- it
should describe the change and wait for you to confirm or run it yourself,
not apply it silently.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
