# Template Reference

> [!IMPORTANT]
> **Seeded, not authored**: `scripts/bootstrap_template.py` copies this checkpoint from the
> tracked seed `.agents/templates/template-ref.md` into `.agents/TEMPLATE_REF.md`. Unlike
> `.agent-state.md`, the copy is **committed** -- it is a durable record, not a scratchpad.
> Edit the copy freely; edit the seed only when changing the starting structure for every
> new project.

This repository's AI-agent governance files (`AGENTS.md`, `.agents/`, `CLAUDE.md`, `.claude/`,
and the other provider redirects) were established from `ai-agent-template` and have **no
automated relationship to it**. Nothing here pulls updates from upstream, and nothing upstream
knows this repository exists. That template is maintained as the shared "lessons learned"
reference for AI-agent rules across projects; this file is the manual checkpoint that makes
drift from it deliberate instead of silent.

**Reference repo**: <https://github.com/peterrichards-lr/ai-agent-template>
**Reference version at last check**: `unknown` (origin/main @ `unknown`, unknown)
**Last checked**: never

> A stamp of `unknown` / `never` means no baseline has been recorded yet -- expected
> immediately after bootstrap, because a repository created with GitHub's "Use this template"
> has no shared history with the template to read a commit from. Run the drift checker with
> `--update-stamp` to set the baseline.

---

## Checking for drift

```bash
python3 scripts/check_template_drift.py                 # report only
python3 scripts/check_template_drift.py --update-stamp  # report, then move the stamp forward
python3 scripts/check_template_drift.py --fail-on-drift # report, exit 2 on drift (for CI)
```

The script clones the upstream template, lists what changed there since the commit recorded
above, and diffs the governed paths (`.agents/skills/`, `.agents/subagents/`,
`.agents/templates/`, `AGENTS.md`, `scripts/`, `.github/workflows/`, `.pre-commit-config.yaml`)
against the local copies, ignoring `Last Updated` / `Last Reviewed` footers. With no network it
prints a warning and exits 0 -- an offline checkout must never fail a build over this.

Reading the report is not the same as acting on it. For each real divergence, either adopt the
upstream change or record it below as a deliberate decision with a linked issue.

---

## Known drift as of this check

Each entry is a real, linked issue in **this** repository -- not a note-to-self. An empty list
means the last comparison found nothing, not that no comparison has happened; the "Last checked"
date above is the authority on that.

- _None recorded yet. Run the drift checker to populate this list._

<!--
Example entries, kept commented out so the seeded list starts clean:

- [#931](https://github.com/owner/<PROJECT_NAME_PLACEHOLDER>/issues/931) - release branch naming
  disagrees between the release script and `CONTRIBUTING.md`.
- [#932](https://github.com/owner/<PROJECT_NAME_PLACEHOLDER>/issues/932) - the same test-safety rule
  is stated with different strictness across three files, and the file designated as the single
  source of truth is the stale one. `AGENTS.md` itself states "single source of truth per
  topic... if you see the same rule stated differently in two places, that's a bug" -- so this
  repository is in violation of its own stated principle.
-->

---

## Deliberate divergence

Rules this repository has intentionally chosen **not** to inherit. Recording them here stops a
future drift check from re-litigating a decision that was already made, and stops an agent from
"fixing" the divergence back to the upstream wording.

- _None recorded yet._

---

## How to use this file: the contract runs both ways

**Downstream (template → here).** Before writing a new agent rule in `<PROJECT_NAME_PLACEHOLDER>`,
check whether `ai-agent-template` already documents a corrected or newer version of the same
rule. The template exists because these rules are expensive to get right, and most of them were
hardened by a real incident somewhere. Inheriting a corrected rule costs a `git diff`; rewriting
it from scratch costs the incident again.

**Upstream (here → template).** If you find and fix a real process bug here -- an agent rule that
does not bind behaviour, a check that passes when it should fail, a guardrail that was missing --
consider whether the same lesson belongs in `ai-agent-template`, so the next repository does not
inherit the same bug. Open an issue there describing the failure you actually observed, not the
rule you would like added. This direction is the one that gets skipped, and it is the one that
makes the template worth having.

Update the "Last checked" stamp and the drift list above whenever this comparison is repeated.
`.agents/skills/template-sync/SKILL.md` states the full contract and when an agent must load it.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
