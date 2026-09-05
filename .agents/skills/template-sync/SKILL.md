---
name: template-sync
description: >-
  Governs the bidirectional contract with the upstream AI agent template: consult it before
  writing a new agent rule locally, and push lessons learned back upstream. Load before
  authoring or amending any agent rule, skill, or guardrail, and when running the drift check.
---

# Skill: Upstream Template Synchronisation

A repository bootstrapped from `ai-agent-template` inherits its agent governance **once**.
Nothing pulls updates afterwards, and nothing upstream knows this repository exists. Left
alone, that produces two symmetrical failures:

- a rule the template corrected after a real incident stays wrong here, forever;
- a process bug found and fixed here is never carried upstream, so the next project
  inherits it.

[`.agents/TEMPLATE_REF.md`](../../TEMPLATE_REF.md) is the deliberate manual checkpoint against
both. It records the upstream repository, the exact version and commit last compared against,
a known-drift list whose entries link real issues, and the divergences this repository has
chosen on purpose.

---

## Directives & Rules of Engagement

### 1. Check Upstream Before Writing a New Rule (Downstream Direction)

**TRIGGER**: before authoring or materially amending any agent rule -- a new `SKILL.md`, a new
directive inside one, a new entry in the `AGENTS.md` routing table, a new guardrail script, or
a new CI gate.

**MANDATORY**: consult the upstream template first and cite what you found.

1. Read the version stamp in `.agents/TEMPLATE_REF.md` so you know what you last compared against.
2. Run `python3 scripts/check_template_drift.py` and read the report.
3. Check whether the upstream already documents a corrected or newer version of the rule you
   are about to write.
4. State the outcome explicitly: *"upstream has no equivalent rule"*, *"adopting the upstream
   wording"*, or *"deliberately diverging because X"*.

Most rules in the template were hardened by a real incident somewhere. Inheriting a corrected
rule costs a `git diff`. Rewriting it from memory costs the incident again.

> [!WARNING]
> An unread report is not a check. Per `.agents/skills/no-assumptions/SKILL.md`, "the template
> probably doesn't cover this" is a forbidden claim: run the script and read the output.

### 2. Push Lessons Learned Back (Upstream Direction)

**TRIGGER**: you fixed a real process bug in this repository -- an agent rule that did not bind
behaviour, a check that passed when it should have failed, a guardrail that was missing, a
timestamp or attribution mechanism that silently drifted.

**MANDATORY**: before closing the work, decide out loud whether the same lesson belongs upstream,
and open an issue on the template when it does. Describe **the failure you actually observed**,
not the rule you would like added -- the observed failure is what makes the rule defensible to
the next reader.

This is the direction that gets skipped, because nothing local fails when you skip it. It is
also the direction that makes the template worth having.

### 3. Record Divergence; Never Leave It Implicit

Every real difference from upstream is one of exactly two things, and must be written down as
such in `.agents/TEMPLATE_REF.md`:

| Kind | Where it goes | What it needs |
| :--- | :--- | :--- |
| Drift to fix | **Known drift as of this check** | A linked issue **in this repository**, not a note-to-self |
| Chosen difference | **Deliberate divergence** | One sentence of justification |

An undocumented difference is the worst of the three states: the next drift check re-reports it,
the next agent "fixes" it back to the upstream wording, and the decision behind it is lost.

### 4. Running the Drift Check

```bash
python3 scripts/check_template_drift.py                 # report only, never writes
python3 scripts/check_template_drift.py --update-stamp  # report, then move the stamp forward
python3 scripts/check_template_drift.py --fail-on-drift # report, exit 2 on drift (CI gate)
```

- The script is **read-only by default**. It rewrites the stamp only with `--update-stamp`, or
  after an interactive `y` when a human is at a TTY.
- **Offline is not a failure.** With no network it prints a warning and exits `0`, by design: a
  governance helper that fails a build over a DNS lookup gets disabled, and a disabled check
  protects nothing. Exit `1` means the reference file is missing or unparseable -- a real,
  actionable configuration error.
- Only `--update-stamp` after acting on the report. Moving the stamp forward with the drift list
  untouched records a comparison that never happened.

### 5. Do Not Reinvent the Reference File

`.agents/TEMPLATE_REF.md` is seeded by `scripts/bootstrap_template.py` from the tracked template
`.agents/templates/template-ref.md`. If it is missing, copy the seed rather than writing a new
one from scratch: the stanza format is what `scripts/check_template_drift.py` parses, and three
sibling repositories already hand-maintain the same format.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
