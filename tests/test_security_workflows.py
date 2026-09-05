"""
test_security_workflows.py - Unit Test Suite for the SAST & Dependency Security Layer

Covers .github/workflows/security-scan.yml (Semgrep SAST + dependency review),
the .semgrep.yaml project-rule stub, the bootstrapper's per-language Semgrep
ruleset selection, and the docs describing the layer's non-blocking posture.

Deliberately a dedicated module rather than an addition to
tests/test_template_scripts.py: the security layer evolves independently of the
template automation scripts, and pytest auto-discovers tests/test_*.py.
"""

import json
import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).parent.parent
WORKFLOWS_DIR = ROOT_DIR / '.github' / 'workflows'
SECURITY_WORKFLOW = WORKFLOWS_DIR / 'security-scan.yml'
SEMGREP_RULES_FILE = ROOT_DIR / '.semgrep.yaml'
RULESETS_DIR = ROOT_DIR / '.github' / 'rulesets'

# Job ids the security workflow is expected to define.
SEMGREP_JOB_ID = 'semgrep'
DEPENDENCY_REVIEW_JOB_ID = 'dependency-review'

sys.path.insert(0, str(ROOT_DIR / 'scripts'))


def load_workflow(path: Path) -> dict:
    """Parse a workflow file, tolerating YAML 1.1 coercion of the `on:` key to True."""
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if True in data and 'on' not in data:
        data['on'] = data.pop(True)
    return data


def collect_run_scripts(job: dict) -> str:
    """Concatenate every `run:` block and `uses:` reference in a job's steps."""
    fragments = []
    for step in job.get('steps', []):
        if not isinstance(step, dict):
            continue
        for key in ('run', 'uses'):
            value = step.get(key)
            if isinstance(value, str):
                fragments.append(value)
    return "\n".join(fragments)


def test_security_scan_workflow_is_present_and_defines_both_scanners():
    assert SECURITY_WORKFLOW.exists(), "Expected .github/workflows/security-scan.yml to exist"

    workflow = load_workflow(SECURITY_WORKFLOW)
    jobs = workflow.get('jobs', {})

    assert SEMGREP_JOB_ID in jobs, f"Expected a '{SEMGREP_JOB_ID}' job in security-scan.yml"
    assert DEPENDENCY_REVIEW_JOB_ID in jobs, (
        f"Expected a '{DEPENDENCY_REVIEW_JOB_ID}' job in security-scan.yml"
    )

    dependency_review_steps = collect_run_scripts(jobs[DEPENDENCY_REVIEW_JOB_ID])
    assert 'actions/dependency-review-action' in dependency_review_steps


def test_security_scan_jobs_are_non_blocking():
    """Both scanners must surface findings without gating a pull request."""
    jobs = load_workflow(SECURITY_WORKFLOW).get('jobs', {})

    for job_id in (SEMGREP_JOB_ID, DEPENDENCY_REVIEW_JOB_ID):
        assert jobs[job_id].get('continue-on-error') is True, (
            f"Job '{job_id}' must set continue-on-error: true so a finding in a "
            f"third-party dependency never blocks a freshly bootstrapped repository"
        )


def test_semgrep_job_disables_telemetry():
    jobs = load_workflow(SECURITY_WORKFLOW).get('jobs', {})
    semgrep_env = jobs[SEMGREP_JOB_ID].get('env', {})

    assert semgrep_env.get('SEMGREP_SEND_METRICS') == 'off'


def test_security_scan_cancels_superseded_runs():
    """Non-required workflows cancel in progress; required ones must not (see #30)."""
    workflow = load_workflow(SECURITY_WORKFLOW)
    concurrency = workflow.get('concurrency', {})

    assert concurrency.get('cancel-in-progress') is True, (
        "security-scan.yml supplies no required status check, so superseded runs "
        "must be cancelled rather than queued"
    )

    for required_workflow in ('ci.yml', 'issue-link-check.yml', 'pr-scope-check.yml'):
        required = load_workflow(WORKFLOWS_DIR / required_workflow)
        assert required.get('concurrency', {}).get('cancel-in-progress') is False, (
            f"{required_workflow} supplies a required status check and must keep "
            f"cancel-in-progress: false"
        )


def test_security_scan_declares_least_privilege_permissions():
    workflow = load_workflow(SECURITY_WORKFLOW)

    assert workflow.get('permissions') == {'contents': 'read'}, (
        "Top-level permissions must default to read-only contents"
    )

    jobs = workflow.get('jobs', {})
    semgrep_permissions = jobs[SEMGREP_JOB_ID].get('permissions', {})
    assert semgrep_permissions.get('contents') == 'read'
    assert semgrep_permissions.get('security-events') == 'write', (
        "The Semgrep job uploads SARIF and needs security-events: write"
    )

    dependency_review_permissions = jobs[DEPENDENCY_REVIEW_JOB_ID].get('permissions', {})
    assert dependency_review_permissions.get('contents') == 'read'
    assert 'security-events' not in dependency_review_permissions, (
        "The dependency review job writes no SARIF and must not request "
        "security-events: write"
    )


def test_dependency_review_is_scoped_to_pull_requests():
    jobs = load_workflow(SECURITY_WORKFLOW).get('jobs', {})
    condition = jobs[DEPENDENCY_REVIEW_JOB_ID].get('if', '')

    assert "github.event_name == 'pull_request'" in condition, (
        "actions/dependency-review-action only supports pull_request events"
    )


def test_security_scan_jobs_are_not_required_status_checks():
    """Adding a non-blocking scanner as a required check would change merge semantics."""
    workflow = load_workflow(SECURITY_WORKFLOW)
    security_contexts = set()
    for job_id, job in workflow.get('jobs', {}).items():
        security_contexts.add(job.get('name', job_id) if isinstance(job, dict) else job_id)

    for ruleset_file in RULESETS_DIR.glob('*.json'):
        data = json.loads(ruleset_file.read_text(encoding='utf-8'))
        for rule in data.get('rules', []):
            if rule.get('type') != 'required_status_checks':
                continue
            required = {
                check.get('context')
                for check in rule.get('parameters', {}).get('required_status_checks', [])
            }
            overlap = required & security_contexts
            assert not overlap, (
                f"{ruleset_file.name} requires non-blocking security job(s) {sorted(overlap)}; "
                f"a continue-on-error scanner must not be a required status check"
            )


def test_semgrep_scan_consumes_the_project_rule_file():
    jobs = load_workflow(SECURITY_WORKFLOW).get('jobs', {})
    semgrep_steps = collect_run_scripts(jobs[SEMGREP_JOB_ID])

    assert '.semgrep.yaml' in semgrep_steps, (
        "The Semgrep job must scan with the project's own rules, not only registry packs"
    )
    assert 'SEMGREP_RULESETS' in semgrep_steps or 'SEMGREP_RULESETS' in yaml.dump(jobs), (
        "Registry rulesets must be declared in a single SEMGREP_RULESETS knob the "
        "bootstrapper can rewrite per language stack"
    )


def test_semgrep_stub_ships_exactly_one_worked_example_rule():
    assert SEMGREP_RULES_FILE.exists(), "Expected a .semgrep.yaml project-rule stub"

    rules = (yaml.safe_load(SEMGREP_RULES_FILE.read_text(encoding='utf-8')) or {}).get('rules', [])
    assert len(rules) == 1, "The stub ships exactly one active worked example rule"

    rule = rules[0]
    for key in ('id', 'message', 'languages', 'severity'):
        assert key in rule, f"Semgrep rule is missing required key '{key}'"
    assert 'pattern' in rule or 'patterns' in rule or 'pattern-either' in rule

    assert 'coding-standards' in rule['message'], (
        "The worked example must cite the prose rule it mechanises so adopters see "
        "the skill-file-to-Semgrep-rule link"
    )


def test_semgrep_stub_is_commented_guidance():
    content = SEMGREP_RULES_FILE.read_text(encoding='utf-8')
    comment_lines = [line for line in content.splitlines() if line.lstrip().startswith('#')]

    assert len(comment_lines) >= 20, (
        "The stub is primarily documentation: adopters need to see how to add a rule"
    )
    assert 'semgrep scan --config .semgrep.yaml' in content, (
        "The stub must document how to run the project rules locally"
    )
    assert '# - id:' in content, (
        "The stub must carry a commented-out second example rule to copy from"
    )


def test_coding_standards_skill_mandates_mechanised_rules():
    skill = (ROOT_DIR / '.agents' / 'skills' / 'coding-standards' / 'SKILL.md').read_text(encoding='utf-8')

    assert '.semgrep.yaml' in skill, (
        "coding-standards/SKILL.md must point agents at the project rule file"
    )
    assert 'pattern-matcher' in skill
    assert 'rather than only prose' in skill


def test_security_policy_documents_the_scanner_layer():
    policy = (ROOT_DIR / 'SECURITY.md').read_text(encoding='utf-8')

    assert 'Semgrep' in policy
    assert 'dependency-review' in policy
    assert 'non-blocking' in policy


def test_bootstrap_selects_semgrep_rulesets_per_language():
    from bootstrap_template import SEMGREP_LANGUAGE_RULESETS, SUPPORTED_LANGUAGES

    for language in SUPPORTED_LANGUAGES:
        assert language in SEMGREP_LANGUAGE_RULESETS, (
            f"Language '{language}' has no Semgrep ruleset mapping"
        )

    assert 'p/python' in SEMGREP_LANGUAGE_RULESETS['python']
    assert 'p/golang' in SEMGREP_LANGUAGE_RULESETS['go']
    assert 'p/javascript' in SEMGREP_LANGUAGE_RULESETS['node']
    assert SEMGREP_LANGUAGE_RULESETS['generic'] == [], (
        "The generic profile adds no language pack beyond the shared baseline"
    )


def test_configure_semgrep_rulesets_rewrites_the_workflow(tmp_path):
    from bootstrap_template import configure_semgrep_rulesets

    workflow_path = tmp_path / '.github' / 'workflows' / 'security-scan.yml'
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text(
        "jobs:\n"
        "  semgrep:\n"
        "    env:\n"
        "      SEMGREP_RULESETS: \"p/ci p/secrets\"\n",
        encoding='utf-8'
    )

    assert configure_semgrep_rulesets(tmp_path, 'python') is True

    updated = workflow_path.read_text(encoding='utf-8')
    assert 'SEMGREP_RULESETS: "p/ci p/secrets p/python"' in updated

    # Idempotent: re-running for another stack replaces rather than appends.
    assert configure_semgrep_rulesets(tmp_path, 'go') is True
    updated_again = workflow_path.read_text(encoding='utf-8')
    assert 'SEMGREP_RULESETS: "p/ci p/secrets p/golang"' in updated_again
    assert 'p/python' not in updated_again


def test_configure_semgrep_rulesets_is_a_no_op_when_workflow_removed(tmp_path):
    from bootstrap_template import configure_semgrep_rulesets

    assert configure_semgrep_rulesets(tmp_path, 'python') is False


def test_shipped_workflow_matches_the_generic_baseline():
    """The template ships the generic profile; bootstrap adds the language pack."""
    from bootstrap_template import SEMGREP_BASELINE_RULESETS

    jobs = load_workflow(SECURITY_WORKFLOW).get('jobs', {})
    shipped = jobs[SEMGREP_JOB_ID].get('env', {}).get('SEMGREP_RULESETS', '')

    assert shipped.split() == SEMGREP_BASELINE_RULESETS
