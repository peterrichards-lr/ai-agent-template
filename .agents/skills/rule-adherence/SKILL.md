---
name: rule-adherence
description: >-
  Enforces explicit self-verification against prose rules, checkable artifacts, and visible self-correction.
  Load before high-commitment actions like merging, deploying, or declaring tasks complete.
---

# Skill: Rule Adherence & Self-Verification

---

## Directives & Rules of Engagement

### 1. Prose Rules Are Not Reliably Followed -- Not Even By The Agent That Wrote Them
This isn't hypothetical. This template's own history has documented cases of an agent writing a rule and then failing to follow it within the same session -- e.g. documenting "every PR must close an issue" and skipping it on the next several PRs regardless, or documenting "stay on a failing PR until it's green" and then, minutes later, pushing a fix commit into a PR that had already merged without checking its state first. A rule read 50 turns ago is not "in mind" the way the last few tool results are; long sessions dilute earlier context, and nothing about having written a rule makes an agent immune to forgetting it.

### 2. Re-Read Before You Act, Don't Rely on Memory
Immediately before a high-commitment action, re-open and re-read the specific skill file(s) that govern it -- don't trust your recollection of having internalized it earlier in the session. This costs a few seconds and a small amount of context; skipping it is how rules get silently dropped.

### 3. Prefer Checkable Artifacts Over Memory
For any MUST-rule that produces something checkable -- a PR body string, a required file, a label, a commit message pattern -- add a CI check for it rather than leaving it as a prose reminder (see `.github/workflows/issue-link-check.yml` for the pattern this template already uses). If a rule genuinely can't be made checkable, say so explicitly wherever it's documented: mark it as advisory, not enforced, so a human reviewing the agent's work knows to verify it themselves rather than assume it happened.

### 4. Collapse Multi-Step Sequences Into One Tool Call Where Possible
A remembered sequence ("do A, then B, then C") is more likely to be partially skipped than a single tool invocation that performs the whole thing. Where a rule requires several actions in sequence -- e.g. post a plan summary, then later post the answer to an open question, then a revised plan if it changed (`reflection-and-planning/SKILL.md` rule 3) -- prefer a helper script or combined action over asking the agent to remember each step individually, wherever one can reasonably be built.

### 5. If You Catch Yourself Having Skipped a Rule, Say So and Fix It
Discovering mid-session that an earlier action didn't follow a documented rule is not a reason to quietly continue. Treat it exactly like discovering a bug: name it explicitly to the human, and remediate retroactively as its own visible step (file the issue that should have existed, add the missing comment, close the loop) rather than leaving it silently incomplete.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-04* | *Last Reviewed: 2026-09-04*
