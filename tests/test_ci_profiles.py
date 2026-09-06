"""
test_ci_profiles.py - Per-Language CI Workflow Profile Suite

`bootstrap_template.py --lang go` used to leave a workflow named "CI Quality Gate"
that installed Python, ran this template's own pytest suite and never compiled a line
of Go. These tests hold the fix in place: a CI profile ships for every language
`--lang` accepts, bootstrap installs the matching one, and each profile keeps the
structure that makes path filtering safe under a required-status-check ruleset.

The three structural invariants, all of which have a specific failure behind them:

1. **The doc checks are never filtered.** PR #75 filtered the whole workflow and was
   reverted before merge: `ci.yml` was entirely documentation validation, so excluding
   `**/*.md` disabled the skill-routing drift test, the provider-redirect check, the
   doc-footer guard and markdownlint for exactly the pull requests those exist to
   catch. Only the heavy language build sits behind the filter. See #42, #44.
2. **The filtered job is paired with a same-named skip job, and a broken filter fails
   loudly.** A failed `needs:` skips a dependent job whatever its `if:` says, unless
   that condition is `always()`/`!cancelled()` -- so without `always()` on the skip
   twin, a filter failure would skip both jobs and the required context would simply
   never report. That relocates the deadlock rather than removing it.
3. **No matrix on a job whose name is (or could become) a required context.** GitHub
   reports a matrix job's context as `name (matrix-values)`, never the bare `name`, so
   a ruleset requiring the bare name waits forever and the #66 context validator fails
   it as unmatched.

Deliberately a dedicated module rather than an addition to
tests/test_template_scripts.py: these assertions are about the shipped workflow
profiles, which evolve with the CI posture rather than with the automation scripts.
pytest auto-discovers tests/test_*.py.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from bootstrap_template import (  # noqa: E402
    BUILD_AND_TEST_JOB_NAME,
    CI_PROFILE_DIR_RELPATH,
    CI_WORKFLOW_RELPATH,
    QUALITY_GATE_JOB_NAME,
    SUPPORTED_LANGUAGES,
    clean_ci_profile_library,
    configure_ci_workflow,
)

# Reused rather than restated: the pinning policy has exactly one definition, in the
# module that enforces it for .github/workflows. A second copy of these patterns here
# would drift the moment the policy tightened.
from test_workflow_pinning import (  # noqa: E402
    SHA_PINNED_PATTERN,
    USES_LINE_PATTERN,
    VERSION_COMMENT_PATTERN,
)

ROOT_DIR = Path(__file__).parent.parent
PROFILE_DIR = ROOT_DIR / CI_PROFILE_DIR_RELPATH
SHIPPED_CI_WORKFLOW = ROOT_DIR / CI_WORKFLOW_RELPATH
BRANCH_PROTECTION_DOC = ROOT_DIR / 'docs' / 'BRANCH_PROTECTION.md'

# `make verify` expands to lint + test + docs, and lint expands to lint-tooling +
# lint-lang. Between them the two CI jobs must invoke that whole chain, or CI is a
# weaker gate than the `make verify` a contributor runs locally.
VERIFY_CHAIN_TARGETS = {'lint-tooling', 'lint-lang', 'test', 'docs'}

# Ecosystem commands that must live in the Makefile's language profile block and
# nowhere else. A profile that spells one out here has forked the recipe, and the two
# copies drift the moment either is edited -- which is the failure the task runner
# (#46) was introduced to remove.
FORBIDDEN_RUN_TOKENS = [
    'pytest',
    'cargo ',
    'go test',
    'go vet',
    'go build',
    'npm ',
    'mvn ',
    'gradlew',
    'ctest',
    'cmake ',
    'pip install',
    'pre-commit run',
]

MAKE_INVOCATION_PATTERN = re.compile(r'(?:^|\s)make\s+([a-z0-9\- ]+)')


def load_profile(path: Path) -> dict:
    """Parse a profile, tolerating YAML 1.1 coercion of the `on:` key to True."""
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if True in data and 'on' not in data:
        data['on'] = data.pop(True)
    return data


def profile_paths() -> list[Path]:
    paths = sorted(PROFILE_DIR.glob('*.yml'))
    assert paths, f"Expected CI workflow profiles in {CI_PROFILE_DIR_RELPATH.as_posix()}"
    return paths


def jobs_named(profile: dict, name: str) -> dict:
    return {
        job_id: job
        for job_id, job in profile.get('jobs', {}).items()
        if isinstance(job, dict) and job.get('name') == name
    }


def run_blocks(profile: dict) -> list[str]:
    blocks = []
    for job in profile.get('jobs', {}).values():
        for step in job.get('steps', []) or []:
            if isinstance(step, dict) and 'run' in step:
                blocks.append(str(step['run']))
    return blocks


def test_a_ci_profile_ships_for_every_supported_language():
    """Every value --lang accepts must have a CI workflow to install.

    A missing profile is the original bug wearing a new hat: bootstrap would accept
    the language, configure the Makefile for it, and leave the previous stack's CI in
    place.
    """
    shipped = {path.stem for path in profile_paths()}
    supported = set(SUPPORTED_LANGUAGES)

    assert shipped == supported, (
        "Every --lang choice needs a CI profile and every profile needs a --lang "
        f"choice. Missing profiles: {sorted(supported - shipped)}; "
        f"orphaned profiles: {sorted(shipped - supported)}"
    )


def test_every_profile_runs_the_required_quality_gate_unconditionally():
    """The job supplying the required status check must never be filtered or gated."""
    for path in profile_paths():
        profile = load_profile(path)
        gate_jobs = jobs_named(profile, QUALITY_GATE_JOB_NAME)

        assert len(gate_jobs) == 1, (
            f"{path.name} must define exactly one job named "
            f"'{QUALITY_GATE_JOB_NAME}' -- it is a required status check in "
            f".github/rulesets/protect-main-branch.json"
        )

        job_id, job = next(iter(gate_jobs.items()))
        assert 'needs' not in job, (
            f"{path.name}: job '{job_id}' supplies the required status check and must "
            "not depend on the paths filter. PR #75 filtered this job and disabled "
            "markdownlint, the provider-redirect check and the doc-footer guard for "
            "docs-only pull requests -- the exact changes they exist to check."
        )
        assert 'if' not in job, (
            f"{path.name}: job '{job_id}' supplies the required status check and must "
            "run on every push and pull request, so it carries no `if:` condition."
        )


def test_quality_gate_job_is_identical_in_every_profile():
    """The always-run half of CI is template-agnostic, so it cannot vary by language.

    A profile that quietly trimmed a doc check would otherwise ship a weaker gate for
    one language than for the other seven.
    """
    gates = {}
    for path in profile_paths():
        gate_jobs = jobs_named(load_profile(path), QUALITY_GATE_JOB_NAME)
        gates[path.name] = next(iter(gate_jobs.values()))

    reference_name, reference_job = next(iter(sorted(gates.items())))
    divergent = [name for name, job in gates.items() if job != reference_job]

    assert not divergent, (
        f"The '{QUALITY_GATE_JOB_NAME}' job is the language-agnostic half of the "
        f"quality gate and must be byte-for-byte the same in every profile. It "
        f"differs from {reference_name} in: {sorted(divergent)}"
    )


def test_only_the_build_job_sits_behind_the_paths_filter():
    """The filter must gate the heavy build and nothing else."""
    for path in profile_paths():
        profile = load_profile(path)
        filtered = {
            job_id
            for job_id, job in profile.get('jobs', {}).items()
            if isinstance(job, dict) and 'filter' in str(job.get('needs', ''))
        }

        assert filtered, f"{path.name} must gate its language build behind a filter job"

        gated_names = {profile['jobs'][job_id].get('name') for job_id in filtered}
        assert gated_names == {BUILD_AND_TEST_JOB_NAME}, (
            f"{path.name}: only '{BUILD_AND_TEST_JOB_NAME}' may sit behind the paths "
            f"filter, but these names do too: {sorted(gated_names)}"
        )


def test_build_job_is_paired_with_a_same_named_skip_job():
    """Exactly one of the pair runs, and both report under the same context name."""
    for path in profile_paths():
        profile = load_profile(path)
        build_jobs = jobs_named(profile, BUILD_AND_TEST_JOB_NAME)

        assert len(build_jobs) == 2, (
            f"{path.name} must declare a build job and a same-named skip twin so a "
            f"docs-only pull request still reports '{BUILD_AND_TEST_JOB_NAME}'. "
            f"Found {len(build_jobs)} job(s) with that name."
        )

        conditions = {job_id: str(job.get('if', '')) for job_id, job in build_jobs.items()}
        runs = [job_id for job_id, cond in conditions.items() if "== 'true'" in cond]
        skips = [job_id for job_id, cond in conditions.items() if "!= 'true'" in cond]

        assert len(runs) == 1 and len(skips) == 1, (
            f"{path.name}: the pair must be mutually exclusive on the filter output, "
            f"so that exactly one of them ever runs. Conditions: {conditions}"
        )


def test_skip_job_survives_and_fails_a_broken_filter_job():
    """A failed filter must produce a red check, not a missing one.

    GitHub skips a dependent job when a `needs:` job fails, whatever the `if:` says,
    unless the condition is `always()` or `!cancelled()`. Without that, a filter
    failure skips the build job *and* its skip twin, nothing reports the context, and
    the deadlock has merely moved.
    """
    for path in profile_paths():
        profile = load_profile(path)
        build_jobs = jobs_named(profile, BUILD_AND_TEST_JOB_NAME)
        skip_id, skip_job = next(
            (job_id, job)
            for job_id, job in build_jobs.items()
            if "!= 'true'" in str(job.get('if', ''))
        )

        assert 'always()' in str(skip_job.get('if', '')), (
            f"{path.name}: job '{skip_id}' must guard its condition with `always()`, "
            "or a failed filter job skips it too and the required context never reports."
        )

        skip_script = '\n'.join(
            str(step['run']) for step in skip_job.get('steps', []) or [] if 'run' in step
        )
        assert 'needs.filter.result' in yaml.dump(skip_job), (
            f"{path.name}: job '{skip_id}' must inspect `needs.filter.result` so it can "
            "tell a documentation-only change from a filter that failed."
        )
        assert 'exit 1' in skip_script, (
            f"{path.name}: job '{skip_id}' must exit non-zero when change detection "
            "failed. Reporting success there would green-light a build that never ran."
        )


def test_no_profile_puts_a_matrix_on_a_named_check_job():
    """A matrix renames the reported context to `name (matrix-values)`.

    A ruleset requiring the bare name would then wait forever, and the context
    validator added in #66 would fail it as unmatched. Aggregate under a fixed-name
    job instead and let a matrix run in a job beneath it.
    """
    protected_names = {QUALITY_GATE_JOB_NAME, BUILD_AND_TEST_JOB_NAME}

    for path in profile_paths():
        profile = load_profile(path)
        offenders = [
            job_id
            for job_id, job in profile.get('jobs', {}).items()
            if isinstance(job, dict)
            and job.get('name') in protected_names
            and 'matrix' in (job.get('strategy') or {})
        ]

        assert not offenders, (
            f"{path.name}: jobs {offenders} carry a build matrix but supply a "
            "fixed-name check context. GitHub reports a matrix job as "
            "'name (matrix-values)', so the bare name would never be reported."
        )


def test_profiles_drive_the_task_runner_rather_than_restating_ecosystem_commands():
    """Ecosystem commands belong in the Makefile profile block, stated exactly once."""
    for path in profile_paths():
        script = '\n'.join(run_blocks(load_profile(path)))
        restated = [token for token in FORBIDDEN_RUN_TOKENS if token in script]

        assert not restated, (
            f"{path.name} restates ecosystem command(s) {restated} that already live "
            "in the Makefile's language profile block. CI must invoke the task runner "
            "verbs so the local gate and the pipeline cannot drift."
        )


def test_profile_make_targets_cover_the_whole_verify_chain():
    """Together the two jobs must run everything `make verify` runs."""
    for path in profile_paths():
        script = '\n'.join(run_blocks(load_profile(path)))
        invoked = set()
        for match in MAKE_INVOCATION_PATTERN.finditer(script):
            invoked.update(match.group(1).split())

        missing = VERIFY_CHAIN_TARGETS - invoked
        assert not missing, (
            f"{path.name} never invokes {sorted(missing)}, so CI is a weaker gate than "
            "the `make verify` a contributor runs locally. verify = lint + test + docs, "
            "and lint = lint-tooling + lint-lang."
        )


def test_every_profile_uses_reference_is_sha_pinned_with_a_version_comment():
    """Profiles are workflows too, and the pinning policy applies before install.

    tests/test_workflow_pinning.py only globs .github/workflows, so an unpinned action
    could otherwise sit in a profile until bootstrap copied it into a live workflow.
    """
    unpinned = []
    for path in profile_paths():
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            match = USES_LINE_PATTERN.match(line)
            if not match:
                continue
            reference, trailer = match.group('reference'), match.group('trailer')
            if not SHA_PINNED_PATTERN.match(reference):
                unpinned.append(f"{path.name}:{line_number}: unpinned {reference}")
            elif not VERSION_COMMENT_PATTERN.match(trailer):
                unpinned.append(f"{path.name}:{line_number}: no version comment {reference}")

    assert not unpinned, (
        "Every `uses:` in a CI profile must be pinned to a full 40-character commit "
        "SHA with a trailing `# vX.Y.Z` comment, exactly as in .github/workflows:\n  "
        + "\n  ".join(unpinned)
    )


def test_shipped_ci_workflow_is_the_python_profile():
    """This repository must run the profile it ships, not a private variant.

    The template is itself a Python project, so `.github/workflows/ci.yml` and the
    python profile are the same file. Anything else means the profiles are untested
    by the repository that publishes them -- which is how the original defect (a Go
    project running a Python CI) survived four downstream adoptions.
    """
    python_profile = PROFILE_DIR / 'python.yml'
    assert python_profile.exists(), "Expected a python CI profile to exist"

    assert SHIPPED_CI_WORKFLOW.read_text(encoding='utf-8') == python_profile.read_text(
        encoding='utf-8'
    ), (
        f"{CI_WORKFLOW_RELPATH.as_posix()} has drifted from "
        f"{(CI_PROFILE_DIR_RELPATH / 'python.yml').as_posix()}. Edit the profile and "
        "copy it into place so this repository keeps dogfooding what it ships."
    )


def test_generic_profile_fails_loudly_instead_of_reporting_a_green_build():
    """--lang generic must not report a passing build over a project with no tests."""
    generic = PROFILE_DIR / 'generic.yml'
    assert generic.exists(), "Expected a generic CI profile to exist"

    body = generic.read_text(encoding='utf-8')
    assert 'make lint-lang test' in body or 'make test' in body, (
        "The generic profile must still invoke `make test`, whose generic Makefile "
        "profile exits non-zero until a real test command is configured. A profile "
        "that skipped the call would report a green build on a project that has never "
        "run a test."
    )


@pytest.fixture
def project_tree(tmp_path):
    """A minimal tree carrying the profile library and a workflow to overwrite."""
    (tmp_path / CI_PROFILE_DIR_RELPATH).mkdir(parents=True)
    (tmp_path / CI_WORKFLOW_RELPATH).parent.mkdir(parents=True)
    for language in SUPPORTED_LANGUAGES:
        shutil.copy(PROFILE_DIR / f'{language}.yml', tmp_path / CI_PROFILE_DIR_RELPATH)
    (tmp_path / CI_WORKFLOW_RELPATH).write_text('name: stale\n', encoding='utf-8')
    return tmp_path


def test_configure_ci_workflow_installs_the_selected_profile(project_tree):
    """--lang go must leave a workflow that builds Go, not one that runs pytest."""
    assert configure_ci_workflow(project_tree, 'go') is True

    installed = (project_tree / CI_WORKFLOW_RELPATH).read_text(encoding='utf-8')
    expected = (PROFILE_DIR / 'go.yml').read_text(encoding='utf-8')
    assert installed == expected
    assert 'setup-go' in installed


def test_configure_ci_workflow_dry_run_leaves_the_workflow_untouched(project_tree):
    assert configure_ci_workflow(project_tree, 'rust', dry_run=True) is True
    assert (project_tree / CI_WORKFLOW_RELPATH).read_text(encoding='utf-8') == 'name: stale\n'


def test_configure_ci_workflow_aborts_when_the_profile_is_missing(project_tree):
    """A silent skip would leave the previous stack's CI in place, looking correct."""
    (project_tree / CI_PROFILE_DIR_RELPATH / 'rust.yml').unlink()

    with pytest.raises(SystemExit):
        configure_ci_workflow(project_tree, 'rust')


def test_clean_template_removes_the_ci_profile_library(project_tree):
    """The seven profiles the adopter did not choose are template scaffolding."""
    removed = clean_ci_profile_library(project_tree)

    assert removed == [CI_PROFILE_DIR_RELPATH.as_posix()]
    assert not (project_tree / CI_PROFILE_DIR_RELPATH).exists()
    assert (project_tree / CI_WORKFLOW_RELPATH).exists(), (
        "The installed workflow must survive; only the unused library is removed."
    )


def test_filter_ships_with_no_documentation_exclusions_active():
    """The filter must exclude nothing until an adopter has checked it is safe to.

    This is the #75 regression expressed as a test. That pull request excluded
    `**/*.md` and thereby disabled every check that reads documentation for exactly
    the changes those checks exist to catch. This template's own test suite reads
    documentation -- the skill-routing tables, the README tree, the provider redirects
    -- so an active exclusion here is a live regression, not a hypothetical one.
    """
    for path in profile_paths():
        profile = load_profile(path)
        for job in profile.get('jobs', {}).values():
            for step in job.get('steps', []) or []:
                if not isinstance(step, dict) or 'paths-filter' not in str(step.get('uses', '')):
                    continue

                patterns = yaml.safe_load(step['with']['filters'])['code']
                negated = [pattern for pattern in patterns if pattern.startswith('!')]

                assert not negated, (
                    f"{path.name}: the shipped paths filter excludes {negated}. Ship "
                    "exclusions commented out: a check behind this filter that reads an "
                    "excluded path silently stops running on the changes it guards."
                )


def test_ruleset_requires_the_build_and_test_context():
    """CI whose failure nobody must act on is decoration.

    The same-named skip twin and the `always()` guard above are what make requiring
    this context safe; without them it would be the deadlock #44 describes.
    """
    ruleset = json.loads(
        (ROOT_DIR / '.github' / 'rulesets' / 'protect-main-branch.json').read_text(encoding='utf-8')
    )
    contexts = {
        check['context']
        for rule in ruleset['rules']
        if rule.get('type') == 'required_status_checks'
        for check in rule['parameters']['required_status_checks']
    }

    assert {QUALITY_GATE_JOB_NAME, BUILD_AND_TEST_JOB_NAME} <= contexts, (
        "protect-main-branch.json must require both CI contexts. Missing: "
        f"{sorted({QUALITY_GATE_JOB_NAME, BUILD_AND_TEST_JOB_NAME} - contexts)}"
    )


def test_branch_protection_docs_explain_the_build_and_test_requirement():
    """Requiring a build an adopter does not have yet must be documented, not sprung."""
    doc = BRANCH_PROTECTION_DOC.read_text(encoding='utf-8')

    assert BUILD_AND_TEST_JOB_NAME in doc, (
        "docs/BRANCH_PROTECTION.md must name the 'Build & Test' context so a reader "
        "can find it in required_status_checks."
    )
    assert 'before importing' in doc.lower(), (
        "docs/BRANCH_PROTECTION.md must tell an adopter whose project cannot build yet "
        "to remove the 'Build & Test' context before importing the ruleset. A required "
        "check nothing can satisfy blocks every pull request, including the one that "
        "would make the build pass."
    )
    assert 'if the filter job itself fails' in doc.lower() or 'always()' in doc, (
        "docs/BRANCH_PROTECTION.md must explain what a failed filter job reports, "
        "since that is what makes requiring this context safe rather than a relocated "
        "deadlock."
    )


def test_every_profile_passes_actionlint():
    """The profiles must be valid workflows before bootstrap installs one.

    A syntax error here surfaces in the adopter's repository on their first push,
    with no local signal at all.
    """
    actionlint = shutil.which('actionlint')
    if actionlint is None:
        pytest.skip("actionlint not installed (pip install -r requirements-dev.txt)")

    result = subprocess.run(
        [actionlint, *[str(path) for path in profile_paths()]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"actionlint rejected a CI profile:\n{result.stdout}{result.stderr}"
