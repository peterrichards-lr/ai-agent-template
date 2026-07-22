"""
test_template_scripts.py - Unit Test Suite for Template Automation Scripts

Tests append_timestamps.py, check_docs_review.py, bootstrap_template.py, and gh_issue_sync.py.
"""

import sys
import json
import pytest
from pathlib import Path

# Add scripts directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from append_timestamps import append_timestamps, should_ignore
from check_docs_review import check_docs, parse_date
from bootstrap_template import configure_language_profile, clean_template_meta_docs
from gh_issue_sync import sync_issues

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
    assert "`go test -v -race ./...`" in updated_content
    assert "<TEST_COMMAND_PLACEHOLDER>" not in updated_content
