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

### Added

- Root `Makefile` task runner exposing one vocabulary in every language stack --
  `setup`, `lint`, `test`, `docs`, `verify`, `push`, `help`. Only the marked language
  profile block varies, and `scripts/bootstrap_template.py --lang <stack>` fills it in (#46).
- `scripts/agent_push.py` behind `make push`: refuses no-op pushes and trees with tracked
  changes left unstaged, rejects flag-shaped commit messages, runs the pre-commit gate
  rather than bypassing it, and checks commit attribution before a commit exists (#46).
- Per-language CI workflow profiles in `.agents/templates/ci/<lang>.yml`, one for every
  `--lang` choice. `scripts/bootstrap_template.py` installs the matching profile over
  `.github/workflows/ci.yml` on every run, so a Go project no longer ships CI that
  installs Python and runs the template's own test suite (#42).
- `Build & Test` job and its same-named `build-and-test-skip` twin behind a
  change-detection `filter` job, plus `{ "context": "Build & Test" }` in
  `.github/rulesets/protect-main-branch.json`. A failed filter exits non-zero through the
  skip twin rather than leaving the required context unreported (#42, #44).

### Changed

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

### Removed

- **Breaking**: `scripts/bootstrap_template.py` no longer accepts `-y` /
  `--non-interactive`. The script has never called `input()`, so the flag suppressed
  nothing; it was quietly a second trigger for template cleanup, so `-y` deleted
  `docs/TEMPLATE_GUIDE.md`, `tests/` and `src/__init__.py` without being asked.
  Passing it is now an argparse usage error raised before any file is touched.
  If you relied on `-y` to clean, pass `--clean-template` explicitly (#90).

### Fixed

- _Nothing yet._

<!--
Example of a released version, kept commented out so the stub starts clean:

## [1.0.0] - 2026-01-31

### Added

- Initial public release (#1).

[1.0.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v1.0.0
-->

[Unreleased]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/compare/main...HEAD

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
