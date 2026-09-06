# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [!IMPORTANT]
> **Adopter stub.** Record changes under `[Unreleased]` as you merge them, then move that
> block under a new version heading when you tag a release. See
> [`.agents/skills/release-management/SKILL.md`](.agents/skills/release-management/SKILL.md)
> for the versioning, release-note, and issue-closure audit rules AI agents must follow.
>
> Categories, in Keep a Changelog order: `Added`, `Changed`, `Deprecated`, `Removed`,
> `Fixed`, `Security`. Delete the categories you do not use in a given release.

## [Unreleased]

### Fixed

- `--clean-template` resets `CHANGELOG.md` to an empty Keep a Changelog stub whose link
  definitions point at the adopter's own repository, so a bootstrapped project no longer
  inherits this template's release history. The file is an input to shipped tooling --
  `scripts/release.py` reads it to draft notes and `--extract-notes` publishes a section
  verbatim -- so an inherited version section collided with the adopter's first release
  rather than merely reading wrong (#105).
- `SECURITY.md` joins the community health files bootstrap substitutes, so a bootstrapped
  project no longer ships a security policy whose opening line names this template. Its
  reporting step now seeds the `--conduct-email` address in place of the untargetable
  "the repository maintainers", giving a reporter a destination the adopter monitors, and
  `scripts/doctor.py` fails the bootstrap if that address is left unresolved (#107).

## [2.0.0] - 2026-09-06

### Added

- Root `Makefile` task runner exposing one vocabulary in every language stack --
  `setup`, `lint`, `test`, `docs`, `verify`, `push`, `help`. Only the marked language
  profile block varies, and `scripts/bootstrap_template.py --lang <stack>` fills it in (#46).
- `scripts/agent_push.py` behind `make push`: refuses no-op pushes and trees with tracked
  changes left unstaged, rejects flag-shaped commit messages, runs the pre-commit gate
  rather than bypassing it, and checks commit attribution before a commit exists (#46).
- `scripts/release.py`: reads the version from `git describe --tags --abbrev=0`, proposes
  the next one from Conventional Commits, and **refuses to write or tag when a `Closes #N`
  in the range points at an issue that is still open or cannot be verified** -- the
  `release-management` rule most likely to be skipped by hand. Drafts the `CHANGELOG.md`
  section, then stops: tagging is a separate confirmed step and the push stays human (#47).
- `.github/workflows/release.yml`: on a `v*` tag push, verifies the tag is annotated,
  well-formed and at the checked-out commit, then publishes the GitHub Release from that
  version's changelog section. Not a required status check (#47).
- Per-language CI workflow profiles in `.agents/templates/ci/<lang>.yml`, one for every
  `--lang` choice. `scripts/bootstrap_template.py` installs the matching profile over
  `.github/workflows/ci.yml` on every run, so a Go project no longer ships CI that
  installs Python and runs the template's own test suite (#42).
- `Build & Test` job and its same-named `build-and-test-skip` twin behind a
  change-detection `filter` job, plus `{ "context": "Build & Test" }` in
  `.github/rulesets/protect-main-branch.json`. A failed filter exits non-zero through the
  skip twin rather than leaving the required context unreported (#42, #44).
- **template-sync**: ship TEMPLATE_REF.md seed, drift checker and template-sync skill (#95)
- **docs**: add opt-in mkdocs-material site with Diátaxis scaffold and Pages workflow (#93)
- **github**: convert issue templates to GitHub Issue Forms (#85)
- **skills**: add always-active no-assumptions and e2e-verification skills (#84)
- **community**: ship community health and editor baseline stubs (#81)
- **scripts**: add commit attribution guard to prevent unmergeable PR deadlock (#79)
- **skills**: add PR review feedback loop rule to github-workflow skill (#77)
- **ci**: add PR scope-sprawl CI gate and coding-standards guardrail (#76, #52)
- **skills**: enforce Fail-First Verification Gate in unit-testing skill (#74)
- **ci**: reject stray and negated closing references in PRs (#73, #29)
- **claude**: ship starter .claude/settings.json client-side deny-list (#72, #40)
- **discovery**: add provider discovery redirects and length gate (#70, #28, #49)
- **claude**: narrow .gitignore and track .claude/skills symlink (#69, #27, #39)
- **skills**: add YAML frontmatter and harmonize routing tables (#68, #38)

### Changed

- `.agents/skills/github-workflow/SKILL.md` rule 4 now states the tracker invariant as
  **one canonical tracker per repo, defaulting to GitHub Issues** rather than mandating
  GitHub Issues specifically, and a new rule 7 documents the external-tracker escape
  hatch (Jira, Azure Boards, Linear, ...): a one-directional mirror rather than a sync,
  which system is authoritative for what, how external IDs are referenced in commits and
  PR bodies, and how the two are kept from drifting. Rule 7 also states plainly that
  `.github/workflows/issue-link-check.yml` and `scripts/check_closing_refs.py` understand
  `Closes #<number>` only, and why that stays deliberate rather than becoming configurable
  (#60).
- `.github/workflows/ci.yml` runs `make verify` instead of restating pytest, `doctor.py`,
  `check_docs_review.py` and `pre-commit`, so the local and CI gates cannot drift (#46).
- `make verify` is now split across two CI jobs rather than one step: `lint-tooling` and
  `docs` always run under the required `Code & Documentation Quality Verification`
  context, while `lint-lang` and `test` run under `Build & Test` behind the paths filter.
  The union is still exactly `make verify`, with nothing dropped and nothing run twice.
  The filter's documentation exclusions ship commented out, because this template's own
  tests read its documentation and excluding `**/*.md` would disable them for precisely
  the pull requests they exist to catch (#42, #44).
- `--clean-template` also removes `.agents/templates/ci/` once the selected profile has
  been installed, alongside the Python scaffolding it already removed (#42, #55).
- The Go profile exports `GOTMPDIR` with `:=` and guards the resolved value before
  building. `GOTMPDIR`, not `-o`, decides where an unsigned test binary first appears on
  disk; `.agents/skills/unit-testing/SKILL.md` taught the incomplete `-o`-only form (#46).
- Bootstrap now denies `Bash(go test*)` wholesale in `.claude/settings.json` for
  `--lang go`, replacing the narrow `Bash(go test)` / `Bash(go test ./...)` pair. Safe
  only because the sanctioned path is now `make test` (#46).
- `AGENTS.md` rule 5, `CONTRIBUTING.md` §3 and `docs/TEMPLATE_GUIDE.md` defer to
  `make test` / `make verify` instead of each restating every ecosystem's commands (#46).
- fix stale GEMINI.md state references across template docs (#64, #37)
- **deps-dev**: bump pre-commit from 4.0.1 to 4.6.2 (#26)
- **deps-dev**: bump pytest from 9.0.3 to 9.1.1
- **deps**: bump actions/checkout from 4 to 7
- **deps**: bump actions/setup-python from 5 to 7

### Removed

- **Breaking**: `scripts/bootstrap_template.py` no longer accepts `-y` /
  `--non-interactive`. The script has never called `input()`, so the flag suppressed
  nothing; it was quietly a second trigger for template cleanup, so `-y` deleted
  `docs/TEMPLATE_GUIDE.md`, `tests/` and `src/__init__.py` without being asked.
  Passing it is now an argparse usage error raised before any file is touched.
  If you relied on `-y` to clean, pass `--clean-template` explicitly (#90).

### Fixed

- `scripts/release.py` no longer restates a curated `[Unreleased]` bullet as a generated
  commit subject beside it. The curated entry cites the issue and the squash commit
  carries the pull request, so the numbers never matched; the drafter now asks `gh` which
  pull request closed each curated issue and drops those commits. The first real run
  against `v1.4.0..HEAD` drafted 24 `### Added` bullets, 18 of them generated; it now
  drafts 20, 13 generated. `--skip-issue-audit` disables the lookup with the audit (#99).
- `scripts/release.py` warns when the curated `[Unreleased]` section describes a breaking
  change -- a `### Removed` entry, or a bullet opening `**Breaking**:` -- that no commit
  declared with `!:` or a `BREAKING CHANGE:` footer. It quotes each offending entry --
  flowed across the bullet's wrapped lines, trimmed on a word boundary and wrapped to the
  report's width -- so the operator can judge it without opening the file. It still
  proposes the level the commits support rather than guessing `major` on prose: the
  mismatch is a judgement about adopter impact, and `--bump major` is where a human
  records it (#99).
- **release**: quote the whole breaking entry and count the warning in a test (#102)
- **bootstrap**: require --name, --repo-owner and --conduct-email at parse time (#92)
- **skills**: pair gh pr view with the gh api call that returns inline review comments (#83)
- **bootstrap**: seed .agent-state.md from a tracked template in fresh clones (#78)
- **ci**: disable cancel-in-progress on required checks and add permissions (#67, #30, #43)
- **rulesets**: reconcile branch protection rulesets and validate check contexts (#66, #41)
- **docs**: repair footer regex, unify fence-stripping, and deduplicate footers (#63, #50)
- **ci**: repair quality gate on main and auto-label Dependabot PRs (#61)

### Security

- **security**: pin GitHub Actions to commit SHAs and add Dependabot cooldown (#88)
- **security**: add non-blocking Semgrep SAST and dependency review layer (#87)

<!--
Example of a released version, kept commented out so the stub starts clean:

## [1.0.0] - 2026-01-31

### Added

- Initial public release (#1).

[1.0.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v1.0.0
-->

[Unreleased]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.0.0

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-06* | *Last Reviewed: 2026-09-06*
