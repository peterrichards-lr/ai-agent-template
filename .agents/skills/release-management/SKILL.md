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

### 5. Git Tags Are the Version; Run the Tooling, Don't Hand-Roll It
The version lives in the annotated `v*` tags and nowhere else. There is deliberately no `VERSION` file: `scripts/check_template_drift.py` already reads `git describe --tags --abbrev=0`, a second source could disagree with it, and a Go project has no version file at all -- tags *are* its version. Where an ecosystem manifest needs a version at build time (`package.json`, `pyproject.toml`, `Cargo.toml`), that value is a one-way projection *from* the tag, never a second source of truth.

Rules 1-4 above are executed by `scripts/release.py`, which is where they stop being prose you can skip:

```bash
python3 scripts/release.py --dry-run   # audit + propose the version; writes nothing, tags nothing
python3 scripts/release.py             # write the CHANGELOG.md section for review
python3 scripts/release.py --tag       # confirm, then create the annotated tag (never pushes)
```

- It reads the current version with `git describe --tags --abbrev=0` and **proposes** the next from Conventional Commits in `<last-tag>..HEAD` (`feat:` minor, `fix:` patch, `!`/`BREAKING CHANGE` major). `--bump {major,minor,patch}` overrides the proposal -- rule 1 is a judgement about adopter impact, and the commit types are only evidence for it.
- It refuses to write or tag when rule 3's audit fails: every `Closes #N` in the range is checked against `gh`, and an issue that is still open -- or whose state cannot be verified -- stops the release (exit code 3).
- It never pushes and never publishes. Pushing the tag stays a human action (rule 4); `.github/workflows/release.yml` then publishes the GitHub Release from that version's `CHANGELOG.md` section on the tag push, satisfying rule 2 even for a tag pushed by hand.

Curated `[Unreleased]` entries are promoted into the new version section verbatim and the generated lines fill in the rest, so the "what changed and why it matters" prose rule 2 asks for survives the automation. Review the drafted section before committing it.

### 6. Release Branches Need a Version Guard This Template Does Not Ship
If you add a long-lived `release/*` branch flow, know the failure mode it brings: GitHub's "Update branch" button can silently revert a release branch's version by cleanly resolving the merge in the default branch's favour, and nothing fails. A dedicated version-guard workflow is the fix. This template has no release branches -- tags are cut from `main` -- so the machinery is not shipped here; add it in the same change as the branch flow, not afterwards.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
