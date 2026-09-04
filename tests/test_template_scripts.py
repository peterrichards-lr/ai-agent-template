"""
test_template_scripts.py - Unit Test Suite for Template Automation Scripts

Tests append_timestamps.py, check_docs_review.py, bootstrap_template.py, and gh_issue_sync.py.
"""

import sys
import json
import yaml
import pytest
from pathlib import Path

# Add scripts directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from append_timestamps import append_timestamps, should_ignore
from check_docs_review import check_docs, parse_date
from bootstrap_template import configure_language_profile, clean_template_meta_docs, get_default_topics
from gh_issue_sync import sync_issues
from setup_branch_protection import apply_branch_protection, validate_ruleset_file

def test_should_ignore_directories(tmp_path):
    assert should_ignore(tmp_path / '.git' / 'README.md') is True
    assert should_ignore(tmp_path / 'node_modules' / 'package.md') is True
    assert should_ignore(tmp_path / '.venv' / 'lib.md') is True
    assert should_ignore(tmp_path / 'docs' / 'guide.md') is False

def test_append_timestamps_injection(tmp_path):
    md_file = tmp_path / 'test_doc.md'
    md_file.write_text("# Test Document\n\nSome content.", encoding='utf-8')

    append_timestamps(tmp_path)

    content = md_file.read_text(encoding='utf-8')
    assert "<!-- markdownlint-disable MD049 -->" in content
    assert "*Last Updated:" in content
    assert "*Last Reviewed:" in content

def test_append_timestamps_underscore_idempotency(tmp_path):
    md_file = tmp_path / 'test_underscore.md'
    md_file.write_text(
        "# Underscore Doc\n\nSome content.\n\n<!-- markdownlint-disable MD049 -->\n---\n_Last Updated: 2026-08-18_ | _Last Reviewed: 2026-08-18_\n",
        encoding='utf-8'
    )

    append_timestamps(tmp_path)

    content = md_file.read_text(encoding='utf-8')
    assert content.count("Last Updated:") == 1

def test_append_timestamps_run_twice_idempotency(tmp_path):
    md_file = tmp_path / 'test_idempotency.md'
    md_file.write_text("# Idempotent Doc\n\nSome content.", encoding='utf-8')

    append_timestamps(tmp_path)
    content_first = md_file.read_text(encoding='utf-8')
    assert content_first.count("Last Updated:") == 1

    append_timestamps(tmp_path)
    content_second = md_file.read_text(encoding='utf-8')
    assert content_second == content_first
    assert content_second.count("Last Updated:") == 1

def test_append_timestamps_paired_negative_fenced_code(tmp_path):
    md_file = tmp_path / 'fenced_only.md'
    md_file.write_text(
        "# Doc with code block only\n\n```markdown\n<!-- markdownlint-disable MD049 -->\n---\n*Last Updated: 2026-08-01* | *Last Reviewed: 2026-08-01*\n```\n",
        encoding='utf-8'
    )

    append_timestamps(tmp_path)

    content = md_file.read_text(encoding='utf-8')
    # A new footer should have been injected outside the code block
    assert content.count("Last Updated:") == 2
    assert check_docs(max_review_days=180, max_update_days=180, max_gap_days=180, root_dir=tmp_path) is True

def test_check_docs_policy(tmp_path):
    valid_md = tmp_path / 'valid.md'
    valid_md.write_text(
        "# Valid Doc\n\nContent\n\n<!-- markdownlint-disable MD049 -->\n---\n*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*\n",
        encoding='utf-8'
    )

    assert check_docs(max_review_days=180, max_update_days=180, max_gap_days=180, root_dir=tmp_path) is True

def test_check_docs_missing_footer(tmp_path):
    invalid_md = tmp_path / 'invalid.md'
    invalid_md.write_text("# Invalid Doc\n\nNo footer here.", encoding='utf-8')

    assert check_docs(max_review_days=180, max_update_days=180, max_gap_days=180, root_dir=tmp_path) is False

def test_check_docs_duplicate_footers(tmp_path):
    dup_md = tmp_path / 'duplicate.md'
    dup_md.write_text(
        "# Dup Doc\n\n*Last Updated: 2026-08-18* | *Last Reviewed: 2026-08-18*\n\n*Last Updated: 2026-08-18* | *Last Reviewed: 2026-08-18*\n",
        encoding='utf-8'
    )
    assert check_docs(max_review_days=180, max_update_days=180, max_gap_days=180, root_dir=tmp_path) is False

def test_check_docs_ignores_fenced_code_blocks(tmp_path):
    code_md = tmp_path / 'code_example.md'
    code_md.write_text(
        "# Doc with Example\n\n```markdown\n*Last Updated: 2026-08-01* | *Last Reviewed: 2026-08-01*\n```\n\n<!-- markdownlint-disable MD049 -->\n---\n*Last Updated: 2026-08-18* | *Last Reviewed: 2026-08-18*\n",
        encoding='utf-8'
    )
    assert check_docs(max_review_days=180, max_update_days=180, max_gap_days=180, root_dir=tmp_path) is True

def test_gh_issue_sync_validation(tmp_path, capsys):
    # Invalid JSON task plan missing title
    plan_data = {
        "epic": {"title": "Test Epic"},
        "tasks": [
            {"body": "Missing title task"},
            {"title": "Valid Task", "body": "Valid body"}
        ]
    }
    plan_file = tmp_path / 'plan.json'
    plan_file.write_text(json.dumps(plan_data), encoding='utf-8')

    sync_issues(plan_file, dry_run=True)

    captured = capsys.readouterr()
    assert "Task #1 is missing a valid title string" in captured.err or "Task #1 is missing a valid title" in captured.out or "Valid Task" in captured.out
    assert "Processed 1 of 2 tasks" in captured.out

def test_clean_template_meta_docs(tmp_path):
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    meta_guide = docs_dir / 'TEMPLATE_GUIDE.md'
    meta_guide.write_text("# Meta Guide", encoding='utf-8')

    clean_template_meta_docs(tmp_path, "TestApp", "go")

    assert not meta_guide.exists()
    readme = tmp_path / 'README.md'
    assert readme.exists()
    assert "# TestApp" in readme.read_text(encoding='utf-8')

def test_configure_language_profile_mutates_agents_md(tmp_path):
    agents_md = tmp_path / 'AGENTS.md'
    initial_text = "# Rules\n\nPrimary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`\n"
    agents_md.write_text(initial_text, encoding='utf-8')

    configure_language_profile(tmp_path, 'go')

    updated_content = agents_md.read_text(encoding='utf-8')
    assert updated_content != initial_text
    assert "go test -v -race ./..." not in updated_content
    assert "go test -c -o" in updated_content
    assert "never bare `go test`" in updated_content
    assert "<TEST_COMMAND_PLACEHOLDER>" not in updated_content

def test_get_default_topics():
    topics_go = get_default_topics('go')
    assert 'ai-agent' in topics_go
    assert 'developer-tools' in topics_go
    assert 'go' in topics_go

    topics_python = get_default_topics('python')
    assert 'ai-agent' in topics_python
    assert 'python' in topics_python

def test_setup_branch_protection_dry_run(tmp_path):
    ruleset_file = tmp_path / 'ruleset.json'
    ruleset_data = {
        "name": "Test Ruleset",
        "target": "branch",
        "enforcement": "active",
        "rules": [{"type": "deletion"}]
    }
    ruleset_file.write_text(json.dumps(ruleset_data), encoding='utf-8')

    assert validate_ruleset_file(ruleset_file) == ruleset_data
    assert apply_branch_protection(ruleset_file, dry_run=True) is True

def extract_workflow_job_contexts(workflows_dir: Path) -> set:
    """Extract check-run contexts emitted by GitHub Actions workflows.

    GitHub reports a check-run context as jobs.<id>.name if present, otherwise <id>.
    """
    contexts = set()
    for wf in workflows_dir.glob('*.y*ml'):
        content = wf.read_text(encoding='utf-8')
        data = yaml.safe_load(content) or {}
        for job_id, job_data in data.get('jobs', {}).items():
            if isinstance(job_data, dict) and 'name' in job_data:
                contexts.add(job_data['name'])
            else:
                contexts.add(job_id)
    return contexts

def validate_ruleset_contexts(ruleset_file: Path, valid_contexts: set):
    """Validate that all required status check contexts in a ruleset match valid contexts."""
    data = json.loads(ruleset_file.read_text(encoding='utf-8'))
    for rule in data.get('rules', []):
        if rule.get('type') == 'required_status_checks':
            checks = rule.get('parameters', {}).get('required_status_checks', [])
            for check in checks:
                context = check.get('context')
                if context not in valid_contexts:
                    raise AssertionError(
                        f"Ruleset {ruleset_file.name} requires status check '{context}', but no matching "
                        f"check-run context was found in workflows. Available: {valid_contexts}"
                    )

def test_ruleset_status_checks_match_workflow_jobs():
    root_dir = Path(__file__).parent.parent
    rulesets_dir = root_dir / '.github' / 'rulesets'
    workflows_dir = root_dir / '.github' / 'workflows'

    valid_contexts = extract_workflow_job_contexts(workflows_dir)
    ruleset_files = list(rulesets_dir.glob('*.json'))
    assert ruleset_files, "No ruleset files found in .github/rulesets/"

    for rf in ruleset_files:
        validate_ruleset_contexts(rf, valid_contexts)

def test_ruleset_validator_rejects_internal_job_id_when_name_present(tmp_path):
    wf_file = tmp_path / 'ci.yml'
    wf_file.write_text(
        "jobs:\n"
        "  quality-gate:\n"
        "    name: Code & Documentation Quality Verification\n",
        encoding='utf-8'
    )
    valid_contexts = extract_workflow_job_contexts(tmp_path)
    assert "Code & Documentation Quality Verification" in valid_contexts
    assert "quality-gate" not in valid_contexts

    bad_ruleset = tmp_path / 'bad-ruleset.json'
    bad_ruleset.write_text(
        json.dumps({
            "name": "Bad Ruleset",
            "rules": [{
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [{"context": "quality-gate"}]
                }
            }]
        }),
        encoding='utf-8'
    )

    with pytest.raises(AssertionError, match="requires status check 'quality-gate'"):
        validate_ruleset_contexts(bad_ruleset, valid_contexts)
