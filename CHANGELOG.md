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

- Blocking line-level project guards: `.guards.json`, checked by `scripts/check_guards.py` as a
  pre-commit hook. Each guard is a regular expression that must never match, with the incident
  that motivated it (`why`) and the remedy (`instead`). Two ship: no local-file URI link in Markdown
  (moved from a pytest test, so it survives `--clean-template`, which deletes `tests/`) and no
  `--no-verify` in automation files. `coding-standards` directive 5 now asks for a guard, added
  with the fix, whenever a fixed bug's shape could recur. `.guards.json` is a governed path for
  the drift check (#181).
- An "Engineering Principles" section in AGENTS.md: five short, editable project defaults (fix
  where the problem is produced; unknown is not absent; finish the change; a green test is not
  the proof; earn every abstraction). "Related References" becomes section 6 (#182).

### Changed

- The AGENTS.md skills routing table is generated from each skill's `SKILL.md` frontmatter
  (`name`, `description`) by `scripts/generate_skill_index.py`, between markers. `make
  skill-index` regenerates it, `make docs` runs it, and a `skill-index` pre-commit hook fails
  when it is stale. The table now has two columns, its rows are sorted by name, and their
  wording is the frontmatter description. `docs/TEMPLATE_GUIDE.md` and the README tree point at
  AGENTS.md instead of restating the list, and the tests that kept the three copies in step are
  removed. An adopter's drift check will show the new table (#180).
- **Behaviour change:** bootstrap now refuses to run while tracked files have uncommitted
  changes, and exits 1 listing them. It rewrites and deletes tracked files (the Makefile
  profile, `ci.yml`, and README and CHANGELOG under `--clean-template`), and git is its backup:
  on a committed tree `git restore .` undoes everything, on a dirty one those edits would be
  lost. Pass `--allow-dirty` to run anyway, as before. `--dry-run` reports the check without
  refusing, and outside a git work tree bootstrap warns instead of assuming the tree is clean
  (#184).

## [2.6.0] - 2026-10-16

### Fixed

- A check listed in `extra.docs_standard.required` now needs everything the profile default
  would require of it, profile keys included, whether or not the profile is recognised. A site
  that listed HOME-LAYOUT, with the profile stylesheet swapped for another in `extra_css` and
  the `related` block deleted, passed with exit 0, because the related requirement applied only
  when the profile itself required HOME-LAYOUT. A site with no related projects no longer lists
  HOME-LAYOUT, or waives it with a reason (#175).
- The Liferay profile's stylesheet is identified by a `docs-profile: liferay` marker line inside
  it, not by its filename. The rendered check finds it anywhere in the built site, so a query
  string, a rename, a moved path, or dropping it from `extra_css` no longer switches the
  profile's required checks off. The drift check finds an unmapped copy by the same marker
  wherever it is kept, so renaming it, deleting its mapping and editing it exits 3 instead of
  "No drift". A copy from before the marker existed is still recognised by its shipped name
  (#164, #162).

## [2.5.0] - 2026-10-16

### Added

- A site can require a specific verification token: `required` and `waive` accept
  `MISSING-VERIFICATION:google` and `MISSING-VERIFICATION:bing`, and the Liferay profile now
  requires Google's. Plain `MISSING-VERIFICATION` was satisfied by either token, so Bing's in
  place of Google's passed with no Google tag on any page, which a site that depends on Search
  Console cannot afford. Waiving `MISSING-VERIFICATION` waives its qualified forms too, so the
  profile's shipped waive still covers a fresh project (#161).
- Dependabot's pull requests skip the docs drift step (a step-level `if` on
  `dependabot[bot]`), so a required docs check reports success rather than pending. They still
  build the site and run `check_docs_rendered.py`, because dependency bumps are what break
  rendering. The template's `.github/dependabot.yml` ignores `mkdocs` versions `>= 2`, which
  remove the plugin system and theme overrides the docs site depends on (#167).

### Changed

- **Docs PR CI compares the shared files against the recorded commit**, as the deploy does:
  `check_template_drift.py --docs-site --fail-on-drift --against-recorded`. Compared against
  upstream HEAD, five template merges in one morning turned every adopter's docs PR red with no
  local change. A local edit to a shared file still fails. `--against-recorded` now falls back
  to HEAD, saying so, when the stamp is `unknown`, instead of exiting 3; a recorded commit the
  template does not have still exits 3. When upstream has a newer release tag than the
  recorded version, the run prints a notice naming it and the shared files it changes, and
  exits 0 (#166).
- The shipped `.github/workflows/docs.yml` is PR CI as well as the deploy: `--docs-site` now
  arms a `pull_request` trigger over the same paths as `push`. A pull request builds the site
  and runs both checks, and never uploads or deploys; it has its own concurrency group, so it
  cannot displace a queued deploy. The drift step is one command, the script's own fallback
  replacing the shell that read the stamp (#166).

### Fixed

- `.github/dependabot.yml` no longer sets `cooldown.semver-major-days` on the `github-actions`
  entry. Dependabot does not support it for that ecosystem and rejected the whole file, so
  Dependabot could not run; the key had shipped since v2.0.0 (#88), and the validator
  caught it when the file next changed. `pip` keeps its 14-day major-version cooldown (#171).
- Under the Liferay profile, a required `HOME-LAYOUT` needs the `related` block itself, not just
  its sub-keys when the block exists. Deleting `extra.docs_standard.related`, together with the
  home page's "Related Liferay tools" section, used to build a site with no related section and
  pass with exit 0; it now fails and names `extra.docs_standard.related`. A site with a reason
  waives `HOME-LAYOUT`, as before. A site with no profile is unchanged (#164).
- The profile stylesheet is recognised in `extra_css` with any query string or fragment
  ignored, so a cache-busting `liferay-blue.css?v=2` no longer hides the profile and its four
  required checks. `SECTION-TITLE` reads the same entries from the build, and now finds a
  suffixed stylesheet's file too (#164).

## [2.4.0] - 2026-10-16

### Added

- A **Docs Site Tests** workflow (`.github/workflows/docs-site-tests.yml`) installs
  `requirements-docs.txt` and runs `tests/test_docs_*.py` on every pull request, so the tests
  that build a real site run in CI. Until now they skipped wherever mkdocs was not installed,
  which was every CI job. These are the #143 section-title fixture, the #146 social and icon
  checks, and the Liferay profile end to end. The job fails if any of them still skips for the
  want of mkdocs. It is the template's own self-test: `--clean-template` removes it with
  `tests/`, and it is not a required status check (#156).

### Changed

- The shipped `.github/workflows/docs.yml` deploy runs the drift check with
  `--against-recorded` when `.agents/TEMPLATE_REF.md` records a real commit, so a template merge
  can no longer block publishing, while a local edit to a shared file still fails. While the
  stamp is still `unknown`, as on a fresh project, it compares against upstream HEAD as before.
  The stamp is read with the drift checker's own parser (#156).
- `check_template_drift.py --docs-site` exits 3 on a profile stylesheet present locally with no
  path mapping, with or without `--fail-on-drift`, like its other "nothing was compared" cases.
  A report-only run used to warn and exit 0 (#156).
- **The Liferay profile requires its four checks by default**: `NO-NOTICE`, `HOME-LAYOUT`,
  `MISSING-VERIFICATION` and `MISSING-SOCIAL`. The profile is known by `liferay-blue.css` in
  `extra_css`, so deleting `required`, or one name in it, no longer turns a check off. A site
  drops a required check only through `extra.docs_standard.waive`, which names the check and
  gives a reason. A waive with no reason, or of a check nothing requires, fails as `REQUIRED`.
  The profile's `site.yml` ships all four waived with their reasons, so a fresh project's first
  deploy passes, and deleting a waive only ever turns a check on. This replaces the profile's
  "checks start off" rule (#155).
- A required check now needs its sub-keys too, and a missing one fails and is named.
  `NO-NOTICE` needs `notice.title`, `text` and `link_text`. `HOME-LAYOUT` with a `related` block
  needs `related.heading`, `intro` and `rows`. A deleted `notice.text`, `notice.link_text` or
  `related.heading` used to leave the check running and checking less, with exit 0 (#155).
- A required `MISSING-SOCIAL` also needs `extra.favicon_svg` and `theme.favicon`, not just
  `extra.social_image` (#155).

## [2.3.1] - 2026-10-16

### Fixed

- `MISSING-SOCIAL` in `check_docs_rendered.py` now checks everything `overrides/main.html`
  emits for link previews and icons, not just `og:image`: `twitter:card` is
  `summary_large_image`, `twitter:image` equals the absolute `og:image`, and the SVG favicon
  (`extra.favicon_svg`), Material's `theme.favicon` and the apple-touch-icon are each linked from
  every page to a file in the build. A broken one used to leave previews and icons failing with
  CI green. Each part is checked only when configured, and the check now runs when
  `extra.social_image`, `extra.favicon_svg` or `theme.favicon` is set; a site that sets none of
  them is unchanged (#146).
- `check_template_drift.py`, a shared file, no longer imports `FOOTER_REGEX` and `IGNORE_DIRS`
  from `check_docs_review.py`, which is not shared and which adopters diverge. v2.3.0 fell back
  to the template's names only when an adopter's copy lacked them, so a copy that defined them
  differently, or failed on import, still changed what the drift check compared. It now
  defines both itself, with the same values. `check_docs_review.FOOTER_REGEX` is unchanged and
  still importable (#147).

## [2.3.0] - 2026-10-16

### Added

- `check_docs_rendered.py`: `extra.docs_standard.required` lists the checks a site cannot do
  without (`MISSING-VERIFICATION`, `MISSING-SOCIAL`, `NO-NOTICE`, `HOME-LAYOUT`). A required
  check with no configuration fails, naming the missing key, instead of being skipped; an
  unknown name fails as `REQUIRED` (#141).
- `check_template_drift.py --against-recorded` compares against the commit recorded in
  `.agents/TEMPLATE_REF.md` instead of upstream HEAD, so a template merge cannot fail a deploy;
  a local edit still does. `docs-site-standard` rule 4 documents the trade-off and where each
  mode belongs (#141).

### Changed

- `scripts/check_template_drift.py` is a shared docs-site file: `--docs-site --fail-on-drift`
  now compares it. It no longer needs an adopter's own `check_docs_review.py` to define
  `FOOTER_REGEX` and `IGNORE_DIRS` (#141).
- `check_docs_rendered.py` refuses a build of fewer than 5 HTML pages (was 3) (#141).

### Fixed

- `--docs-site --fail-on-drift` exits 3 on a profile stylesheet present locally with no path
  mapping, instead of warning and passing with the shared file uncompared (#141).
- The "copy the file FROM" direction is printed only for a shared file whose content differs,
  not for the profile's upstream-only `about.md`, `palette.yml` and `site.yml` (#141).

## [2.2.1] - 2026-10-16

### Fixed

- Section titles in the docs-site nav now render the same with or without an index page. With
  `navigation.indexes`, Material showed a section that has an index page as a link in the
  primary text colour, and one without as a label in the secondary colour, so one stylesheet
  gave liferay-docker-manager white section titles and lfr-tunnel muted ones. The Liferay
  profile's `liferay-blue.css` now gives the link the label's colour at desktop width; hover and
  the active page keep the link colour. The `docs-site-standard` skill states that index pages
  are optional and must render the same, and a new `SECTION-TITLE` check in
  `check_docs_rendered.py` fails a site with an index page whose stylesheets lack the rule, or
  whose markup the rule no longer reaches (#143).
- The `docs-site-standard` skill's shared-files table had the Liferay stylesheet row stranded
  below a paragraph, outside the table.
- `check_docs_rendered.py`'s `UNDATED-PAGE` now accepts a "Last updated" generated from git:
  a page passes with both dates typed in its footer, as before, or with `Last Reviewed` typed
  and the date `mkdocs-git-revision-date-localized-plugin` renders in Material's source-file
  aside, matched by its structure because Material localises its title. A page showing only
  one of the two dates still fails. The `docs-site-standard` skill states both renderings
  (#142).

## [2.2.0] - 2026-10-16

### Added

- Add the `docs-site-standard` skill: the shared MkDocs site standard (home-page layout,
  top-level navigation order, GitHub alerts titled with GitHub's label and a strict title
  lift, shared files never edited downstream), routed from `AGENTS.md` (#135).
- `--docs-site` now seeds the shared docs files: the alerts hook
  `scripts/mkdocs_github_alerts.py`, `overrides/main.html`, `overrides/partials/copyright.html`,
  a generic `docs/about.md`, and `scripts/check_docs_rendered.py`, which checks the built site
  before the Pages upload and is configured from `mkdocs.yml` `extra.docs_standard` (#135).
- `--docs-profile liferay` applies the Liferay tools profile on top of `--docs-site`: the
  `liferay-blue.css` palette, the community-project notice, the About page opening and the
  "Related Liferay tools" rows (#135).
- `check_template_drift.py`: a "Path mapping" section in `.agents/TEMPLATE_REF.md` compares a
  governed file kept at another path; a mismatch prints both SHA-256 prefixes and sizes and
  says which way to copy; `--docs-site` compares only the shared docs files, and names a
  profile stylesheet left unmapped. `overrides/main.html` and `overrides/partials/copyright.html`
  are governed paths (#135).

### Changed

- `check_template_drift.py --fail-on-drift` fails on content differences only. Upstream
  commits since the recorded ref are still reported, but no longer fail the check (#135).
- `check_template_drift.py` exits 3 when nothing could be compared: the upstream repository
  was not found or refused access, or a governed path does not exist upstream. A network
  failure still warns and exits 0 (#135).
- The template's own docs nav follows the standard order and sentence case ("How-to guides",
  "About these docs" last) (#135).
- **deps**: bump github/codeql-action/upload-sarif (#134)
- **deps-dev**: bump actionlint-py from 1.7.12.24 to 1.7.12.25 (#132)

### Fixed

- The `NAV` check in `check_docs_rendered.py` now holds every nav label to sentence case, top
  level and below, as the navigation rule requires; it read only the top level. It skips the
  page's own table of contents, and a proper noun a label needs mid-label goes in
  `extra.docs_standard.proper_nouns` (the Liferay profile lists `Liferay`) (#137, #138).

## [2.1.0] - 2026-09-22

### Added

- Add the `documentation-review` skill to audit existing documentation sets as a body of
  work. While the `documentation` skill enforces post-change hygiene (such as timestamp
  footers and staleness checks), `documentation-review` guides inspecting rendered output,
  auditing documentation against code and CLI help, and correcting navigation and alert
  formatting before restructuring (#122).

### Changed

- In `github-workflow` skill, update CI failure triage instructions to mandate inspecting
  failed logs (`gh run view <id> --log-failed`) and running targeted reruns
  (`gh run rerun <id> --failed`), dropping previous guidance to delete workflow runs (#126, #128).
- Bump `actions/dependency-review-action` from 4.9.0 to 5.0.0 (#119).
- Bump `github/codeql-action/upload-sarif` (#120).

### Fixed

- In `scripts/bootstrap_template.py`, refine placeholder replacement to avoid corrupting
  project URLs and `template-sync` references in `AGENTS.md`, and format seeded conduct
  emails with CommonMark autolink angle brackets (`<email>`) to prevent markdownlint `MD034`
  violations (#123, #124, #128).
- In `scripts/doctor.py`, skip the `.agent-state.md` scratchpad presence check when running
  inside CI environments, preventing checkout failures on fresh, non-interactive CI runs
  where the scratchpad is gitignored (#125, #128).
- In `.github/workflows/security-scan.yml`, guard the `dependency-review` job so it is skipped
  on private repositories without GitHub Advanced Security (GHAS), preventing failing checks
  for private adopter forks (#127, #128).

## [2.0.1] - 2026-09-06

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
- Documents delivered by `--clean-template` no longer cite paths the same run removes.
  `SECURITY.md` argued the SHA-pinning rule is enforced from the inside by linking
  `tests/test_workflow_pinning.py`, which cleanup deletes for every non-Python stack; the
  same shape appeared in `docs/BRANCH_PROTECTION.md` and the `github-workflow` skill. All
  four now make the claim without naming a path the adopter does not have, and
  `tests/test_bootstrap_cleanup.py` asserts the invariant in general -- diffing a real
  `--clean-template` run and rejecting any surviving document that still points at a
  removed path -- rather than guarding the one sentence (#109).
- `AGENTS.md`'s skill routing table now links each `SKILL.md` by repository-relative path.
  Every row had linked its skill twice through an absolute local-file URI (`file:` scheme)
  since the initial commit, which resolves to `/.agents/skills/...` on the filesystem root
  rather than into the repository, so all 26 links pointed at a file on nobody's machine
  and GitHub's renderer
  -- which permits only a small set of URI schemes -- dropped them to unclickable text,
  costing the routing table the navigation it exists to provide. `tests/test_document_links.py`
  asserts the targets resolve to real files and forbids the scheme in any shipped Markdown,
  so the next skill row cannot copy the pattern from the row above it (#110).
- `docs/BRANCH_PROTECTION.md` cites the two issues behind the never-filter-the-doc-checks
  rule as absolute upstream links instead of a bare `See Issues #42 and #44`. The document
  survives `--clean-template` in every stack and GitHub resolves a bare `#N` against the
  repository it is rendered in, so an adopter read a citation silently pointing at their
  own issues 42 and 44. `tests/test_bootstrap_cleanup.py` asserts the general invariant on
  a real bootstrapped tree -- no delivered document may carry a `#N` outside code spans,
  fenced blocks and link text, where GitHub does not autolink -- and that the replacement
  URL survives bootstrap's project rename (#111).

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

[Unreleased]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/compare/v2.6.0...HEAD
[2.6.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.6.0
[2.5.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.5.0
[2.4.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.4.0
[2.3.1]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.3.1
[2.3.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.3.0
[2.2.1]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.2.1
[2.2.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.2.0
[2.1.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.1.0
[2.0.1]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.0.1
[2.0.0]: https://github.com/<GITHUB_OWNER_PLACEHOLDER>/ai-agent-template/releases/tag/v2.0.0

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-10-19* | *Last Reviewed: 2026-10-19*
