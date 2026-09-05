---
name: no-assumptions
description: >-
  Always active. Forbids any technical claim not verified by a tool call made in the current session, including after compaction or resume.
---

# Skill: No Assumptions (Anti-Hallucination Protocol)

> [!CAUTION]
> This skill is **always active**. Unlike every other skill in this repository it has
> no trigger condition, because it has no off state. It **cannot be waived**, overridden,
> or suspended by another skill, a task instruction, a user's urgency, or your own
> judgement that a claim is obviously true.

This file is the single source of truth for the rule stated as universal rule 1 in
[`AGENTS.md`](../../../AGENTS.md).

---

## Directives & Rules of Engagement

### 1. The Core Constraint

Any technical statement, architecture decision, or bug diagnosis MUST be verified against
actual code, configuration, or command output before you act on it or assert it. You are
forbidden from guessing variable names, file paths, API signatures, config keys, dependency
versions, or command behaviour.

### 2. Evidence Must Come From the Current Session

Verification means a **tool call you executed in this session, whose result is in your context
window right now**. Training-data memory is not evidence. A recollection of "I read that file
earlier" is not evidence. Plausibility is not evidence.

> [!IMPORTANT]
> **Compaction and resume corollary.** After a context compaction, a session resume, or any
> point where earlier turns were summarised or pruned, prior tool results **no longer count as
> evidence**. A summary of what a file contained is not the file. If you need the fact again,
> read it again. This is the clause that makes the rule enforceable in long sessions, where
> the failure mode is not guessing but confidently misremembering.

### 3. Verify Before You Speak, Not After

**TRIGGER**: before writing any technical claim about how code works, what a file contains,
what a command returns, what a default value is, or what a previous change accomplished.

**MANDATORY**: identify the claim type below and execute the corresponding tool call *first*.
Wait for the result. Only then write the claim.

| Claim type | Required verification |
| :--- | :--- |
| A file exists, or contains specific content | Read the exact path, or search for the symbol |
| A function, API, or CLI signature | Read the definition -- not the call site, not the docs alone |
| A configuration key or default value | Read the config file or the schema that defines it |
| A dependency's version or behaviour | Read the lockfile / manifest; check the installed version |
| What a previous change did | `git show <sha> --stat`, `git diff`, or `git log` -- not memory |
| A test passed, failed, or is green | The actual test-run output, cited (see `unit-testing/SKILL.md`) |
| A CI job's status | `gh run view` / `gh pr view --json statusCheckRollup` output |
| The system behaves correctly end to end | Real-system evidence (see `e2e-verification/SKILL.md`) |

### 4. Prohibited Phrasing

These phrasings signal an unverified assumption. If you catch yourself writing one, stop,
run the verification, and rewrite the claim around the result:

| Forbidden pattern | Why |
| :--- | :--- |
| *"This should work because..."* | Predicts behaviour with no evidence |
| *"That file probably contains..."* | Guesses file contents |
| *"The API likely returns..."* | Assumes an interface |
| *"As established earlier..."* (without re-reading) | Relies on possibly-pruned context |
| *"This is the standard approach for X"* | Asserts ecosystem behaviour with no cited source |
| *"I believe the default is..."* | Guesses a configuration value |
| *"The fix worked"* (without reading output) | Claims a result that was never observed |

### 5. Declare Uncertainty Instead of Filling It

If the file cannot be read, the command fails, or the tool is unavailable, the correct
response is to **say so and stop** -- never to produce a confident answer anyway:

> "I cannot verify this without reading `<path>`, and I will not speculate. Please confirm it,
> or grant access so I can check directly."

An explicit "I don't know" is a correct answer. A fluent guess is a defect, and it is more
expensive than the question it answered, because everything built on top of it must be redone.

### 6. Scope

Applies to every response, in every skill, with no exception: code explanations, architecture
summaries, debugging hypotheses, root-cause analyses, configuration recommendations, claims
about what a prior change accomplished, and assertions about test or CI state.

Reasonable inference *from evidence already in your context* is permitted and expected.
Confident assertion *without having consulted any evidence* is not.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
