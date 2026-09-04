---
name: release-management
description: >-
  Governs semantic versioning, release notes generation, issue closure auditing, and release verification gates.
  Load when tagging versions or publishing releases.
---

# Skill: Release Management

---

## Directives & Rules of Engagement

### 1. Semantic Versioning
Tag versions as `vMAJOR.MINOR.PATCH`:
- **Patch**: bug fixes, documentation, or internal cleanup with no change to previously-documented agent behavior.
- **Minor**: new rules, new skills, or changes to existing rules that an adopter of this template would need to notice (even if not strictly "breaking" in a code sense -- a rule that now behaves differently is a behavior change).
- **Major**: removing or fundamentally restructuring a skill/rule that existing adopters have built workflows around.

### 2. A Tag Without Release Notes Is An Unchecked Gap
Pushing a bare `git tag` with nothing else is the release equivalent of a PR with no linked issue -- technically fine, practically useless to anyone trying to understand what changed or why. Every version tag MUST be accompanied by a real GitHub Release (`gh release create <tag> --title "..." --notes-file <file>`), not left as a bare ref.

Release notes should describe **what changed and why it matters** -- tie back to the actual problem or motivation where there is one, not just a restatement of commit messages. A reader who wasn't in the session should be able to understand why each change exists.

### 3. Audit Before You Draft
Before writing release notes for a batch of merged work, verify -- don't assume -- that every issue the batch was supposed to close actually closed (`gh issue list --state open` against the numbers you expect to be closed). This is the same "verify, don't assume" principle as `rule-adherence/SKILL.md`, applied at the release checkpoint: it's a natural moment to catch a `Closes #N` that a squash-merge dropped, before it goes unnoticed for another release cycle.

### 4. Tagging Is a High-Commitment Action
Pushing a version tag or publishing a release belongs alongside merging in `human-in-the-loop/SKILL.md`'s High-Risk Operation Gates -- propose the version number and notes, and get confirmation before pushing, rather than tagging silently. This matters even more once `protect-version-tags.json` (see `docs/BRANCH_PROTECTION.md`) is applied to a repo, since tags become immutable: a wrong tag can't be deleted or moved, only superseded by a new one.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-04* | *Last Reviewed: 2026-09-04*
