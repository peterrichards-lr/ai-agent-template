"""
test_template_scripts.py - Unit Test Suite for Template Automation Scripts

Tests append_timestamps.py, check_docs_review.py, bootstrap_template.py, and gh_issue_sync.py.
"""

import fnmatch
import os
import re
import subprocess
import sys
import json
import yaml
import pytest
from pathlib import Path

# Add scripts directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from append_timestamps import append_timestamps, should_ignore
from check_docs_review import check_docs, parse_date, EXTRA_DOC_FILES
from check_docs_review import check_docs, parse_date
from bootstrap_template import (
    configure_language_profile,
    clean_template_meta_docs,
    get_default_topics,
    ensure_claude_skills_symlink,
    configure_claude_settings,
    substitute_community_health_placeholders,
    SUPPORTED_LANGUAGES,
    COMMUNITY_HEALTH_FILES,
    OWNER_PLACEHOLDER,
    CONDUCT_EMAIL_PLACEHOLDER,
    TEMPLATE_PROJECT_NAME,
    ensure_agent_state_scratchpad,
    AGENT_STATE_SEED_RELPATH,
    TEMPLATE_PROJECT_NAME,
)
from gh_issue_sync import sync_issues
from setup_branch_protection import apply_branch_protection, validate_ruleset_file
from check_provider_redirects import check_redirects, MAX_REDIRECT_LINES, REDIRECT_FILES
from check_closing_refs import validate_pr_closing_refs

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

def test_skill_frontmatter_and_routing_tables():
    root_dir = Path(__file__).parent.parent
    skills_dir = root_dir / '.agents' / 'skills'
    agents_md = root_dir / 'AGENTS.md'
    template_guide = root_dir / 'docs' / 'TEMPLATE_GUIDE.md'

    skill_dirs = sorted([d for d in skills_dir.iterdir() if d.is_dir()])
    agents_content = agents_md.read_text(encoding='utf-8')
    guide_content = template_guide.read_text(encoding='utf-8')
    readme_content = (root_dir / 'README.md').read_text(encoding='utf-8')
    skills_section = re.search(r'├── \.agents/skills/.*?(?=├── scripts/)', readme_content, re.DOTALL)
    assert skills_section, "Could not find .agents/skills section in README.md"

    disk = {d.name for d in skill_dirs}
    agents = set(re.findall(r'\*\*\[([a-z0-9-]+)\]', agents_content))
    guide = set(re.findall(r'\*\*`([a-z0-9-]+)`\*\*', guide_content))
    readme = set(re.findall(r'[├└]──\s+([a-z0-9-]+)/', skills_section.group(0)))

    assert disk == agents, f"AGENTS.md drift — only on disk: {disk - agents}; only in table: {agents - disk}"
    assert disk == guide, f"TEMPLATE_GUIDE drift — only on disk: {disk - guide}; only in table: {guide - disk}"
    assert disk == readme, f"README.md tree drift — only on disk: {disk - readme}; only in README: {readme - disk}"

    for s_dir in skill_dirs:
        skill_name = s_dir.name
        skill_file = s_dir / 'SKILL.md'
        assert skill_file.exists(), f"Missing SKILL.md in {s_dir}"

        content = skill_file.read_text(encoding='utf-8')
        assert content.startswith('---\n'), f"{skill_file} missing leading frontmatter delimiter"
        parts = content.split('---\n', 2)
        assert len(parts) >= 3, f"{skill_file} invalid frontmatter structure"

        fm_text = parts[1]
        fm = yaml.safe_load(fm_text)
        assert isinstance(fm, dict), f"{skill_file} frontmatter did not parse to a dict"
        assert fm.get('name') == skill_name, f"{skill_file} frontmatter name '{fm.get('name')}' != directory name '{skill_name}'"
        assert fm.get('description'), f"{skill_file} missing or empty frontmatter description"

def test_claude_skills_symlink_and_gitignore(tmp_path):
    root_dir = Path(__file__).parent.parent
    claude_skills = root_dir / '.claude' / 'skills'

    # 1. Verify repository symlink exists, is relative, and resolves to .agents/skills
    assert claude_skills.is_symlink(), ".claude/skills should be a symlink"
    target = os.readlink(claude_skills).replace('\\', '/')
    assert target == '../.agents/skills', f"Expected relative target '../.agents/skills', got '{target}'"
    assert claude_skills.resolve() == (root_dir / '.agents' / 'skills').resolve()

    skills_on_disk = {d.name for d in (root_dir / '.agents' / 'skills').iterdir() if d.is_dir()}
    skills_via_symlink = {d.name for d in claude_skills.iterdir() if d.is_dir()}
    assert skills_on_disk == skills_via_symlink

    # 2. Test ensure_claude_skills_symlink idempotency and repair
    dummy_root = tmp_path / 'project'
    (dummy_root / '.agents' / 'skills').mkdir(parents=True)
    assert ensure_claude_skills_symlink(dummy_root) is True
    assert (dummy_root / '.claude' / 'skills').is_symlink()
    assert ensure_claude_skills_symlink(dummy_root) is True

    # Repair when pointing to wrong target
    (dummy_root / '.claude' / 'skills').unlink()
    os.symlink('wrong_target', dummy_root / '.claude' / 'skills')
    assert ensure_claude_skills_symlink(dummy_root) is True
    assert os.readlink(dummy_root / '.claude' / 'skills').replace('\\', '/') == '../.agents/skills'

    # 3. Verify .gitignore scoping via git check-ignore individually
    for p in ['.claude/settings.local.json', '.gemini/settings.local.json']:
        res = subprocess.run(['git', 'check-ignore', p], cwd=root_dir, capture_output=True, text=True)
        assert res.returncode == 0, f"Expected {p} to be ignored by git"

    for p in ['.claude/skills', '.claude/settings.json']:
        res = subprocess.run(['git', 'check-ignore', p], cwd=root_dir, capture_output=True, text=True)
        assert res.returncode == 1, f"Expected {p} NOT to be ignored by git"

def test_check_provider_redirects(tmp_path):
    root_dir = Path(__file__).parent.parent
    assert check_redirects(root_dir) is True

    # 1. Failure on missing file
    dummy = tmp_path / 'dummy_repo'
    dummy.mkdir()
    assert check_redirects(dummy) is False

    # 2. Setup valid mock files
    (dummy / '.github').mkdir()
    for f in REDIRECT_FILES:
        (dummy / f).write_text("# Redirect\nSee [`AGENTS.md`](./AGENTS.md)\n", encoding='utf-8')
    assert check_redirects(dummy) is True

    # 3. Line bloat boundary tests (<= MAX_REDIRECT_LINES is allowed, > MAX_REDIRECT_LINES fails)
    exact_content = "\n".join([f"line {i}" for i in range(MAX_REDIRECT_LINES - 1)]) + "\nAGENTS.md\n"
    (dummy / '.cursorrules').write_text(exact_content, encoding='utf-8')
    assert check_redirects(dummy) is True

    bloated_content = "\n".join([f"line {i}" for i in range(MAX_REDIRECT_LINES)]) + "\nAGENTS.md\n"
    (dummy / '.cursorrules').write_text(bloated_content, encoding='utf-8')
    assert check_redirects(dummy) is False

    # 4. Failure on missing AGENTS.md link
    (dummy / '.cursorrules').write_text("# Thin redirect\nNo canonical reference here\n", encoding='utf-8')
    assert check_redirects(dummy) is False

def test_non_md_redirects_timestamp_and_review(tmp_path):
    # Create mock repo with .cursorrules and .windsurfrules lacking footers
    (tmp_path / '.cursorrules').write_text("# Cursor Rules\nRedirect to AGENTS.md\n", encoding='utf-8')
    (tmp_path / '.windsurfrules').write_text("# Windsurf Rules\nRedirect to AGENTS.md\n", encoding='utf-8')

    append_timestamps(tmp_path)
    assert "Last Updated:" in (tmp_path / '.cursorrules').read_text(encoding='utf-8')
    assert "Last Updated:" in (tmp_path / '.windsurfrules').read_text(encoding='utf-8')
    assert check_docs(max_review_days=30, max_update_days=30, max_gap_days=30, root_dir=tmp_path) is True

def test_provider_redirects_doc_drift():
    root_dir = Path(__file__).parent.parent
    agents_content = (root_dir / 'AGENTS.md').read_text(encoding='utf-8')
    readme_content = (root_dir / 'README.md').read_text(encoding='utf-8')
    guide_content = (root_dir / 'docs' / 'TEMPLATE_GUIDE.md').read_text(encoding='utf-8')

    # Note: This check is intentionally forward-only (asserting that every entry in
    # REDIRECT_FILES is referenced in the core docs). Unlike test_skill_frontmatter_and_routing_tables,
    # bidirectional set comparison against prose documents is not practical.
    # Also note that while CLAUDE.md and GEMINI.md appear in multiple unrelated contexts in the docs,
    # this check provides vital drift protection for tool-specific files (.cursorrules,
    # .windsurfrules, .github/copilot-instructions.md).
    for redirect_file in REDIRECT_FILES:
        assert redirect_file in agents_content, f"AGENTS.md missing reference to redirect file '{redirect_file}'"
        assert redirect_file in readme_content, f"README.md missing reference to redirect file '{redirect_file}'"
        assert redirect_file in guide_content, f"TEMPLATE_GUIDE.md missing reference to redirect file '{redirect_file}'"

def test_claude_settings_structure_and_bootstrap(tmp_path):
    root_dir = Path(__file__).parent.parent
    settings_file = root_dir / '.claude' / 'settings.json'

    # 1. Assert baseline repository .claude/settings.json exists and is structured properly
    assert settings_file.exists(), "Missing starter .claude/settings.json"
    data = json.loads(settings_file.read_text(encoding='utf-8'))
    assert "permissions" in data
    permissions = data["permissions"]
    assert isinstance(permissions.get("deny"), list)
    assert isinstance(permissions.get("ask"), list)
    assert isinstance(permissions.get("allow"), list)

    # Validate targeted root/home deny patterns and ensure blanket rm -rf * is absent
    assert "Bash(rm -rf /)" in permissions["deny"]
    assert "Bash(rm -rf /*)" in permissions["deny"]
    assert "Bash(rm -rf ~)" in permissions["deny"]
    assert "Bash(rm -rf ~/*)" in permissions["deny"]
    assert "Bash(rm -rf $HOME)" in permissions["deny"]
    assert "Bash(rm -rf $HOME/*)" in permissions["deny"]
    assert "Bash(rm -rf *)" not in permissions["deny"]

    # Validate anchored force push patterns and ensure unanchored *-f* is absent
    assert "Bash(git push -f)" in permissions["deny"]
    assert "Bash(git push -f *)" in permissions["deny"]
    assert "Bash(git push * -f)" in permissions["deny"]
    assert "Bash(git push * -f *)" in permissions["deny"]
    assert "Bash(git push --force)" in permissions["deny"]
    assert "Bash(git push --force *)" in permissions["deny"]
    assert "Bash(git push * --force)" in permissions["deny"]
    assert "Bash(git push * --force *)" in permissions["deny"]
    assert "Bash(git push *-f*)" not in permissions["deny"]
    assert "Bash(git push *--force*)" not in permissions["deny"]

    # Validate other essential deny patterns
    assert "Bash(docker system prune*)" in permissions["deny"]
    assert "Bash(*DROP DATABASE*)" in permissions["deny"]
    assert "Bash(gh repo delete*)" in permissions["deny"]

    # Validate essential ask patterns (including recoverable git reset --hard)
    assert "Bash(git reset --hard*)" in permissions["ask"]
    assert "Bash(gh pr merge*)" in permissions["ask"]
    assert "Bash(git tag*)" in permissions["ask"]
    assert "Bash(gh release create*)" in permissions["ask"]

    # Validate essential allow patterns
    assert "Bash(pytest*)" in permissions["allow"]
    assert "Bash(pre-commit run*)" in permissions["allow"]

    # 2. Test configure_claude_settings on mock project
    dummy_root = tmp_path / 'project'
    dummy_claude = dummy_root / '.claude'
    dummy_claude.mkdir(parents=True)
    (dummy_claude / 'settings.json').write_text(
        json.dumps({"permissions": {"deny": [], "ask": [], "allow": []}}, indent=2),
        encoding='utf-8'
    )

    # Non-Go stack should not add go test deny
    assert configure_claude_settings(dummy_root, 'python') is True
    res_py = json.loads((dummy_claude / 'settings.json').read_text(encoding='utf-8'))
    assert "Bash(go test)" not in res_py["permissions"]["deny"]
    assert "Bash(go test ./...)" not in res_py["permissions"]["deny"]

    # Go stack should inject narrow bare go test denies, not broad go test*
    assert configure_claude_settings(dummy_root, 'go') is True
    res_go = json.loads((dummy_claude / 'settings.json').read_text(encoding='utf-8'))
    assert "Bash(go test)" in res_go["permissions"]["deny"]
    assert "Bash(go test ./...)" in res_go["permissions"]["deny"]
    assert "Bash(go test*)" not in res_go["permissions"]["deny"]

    # Idempotency check: running again should not duplicate
    assert configure_claude_settings(dummy_root, 'go') is True
    res_idempotent = json.loads((dummy_claude / 'settings.json').read_text(encoding='utf-8'))
    assert res_idempotent["permissions"]["deny"].count("Bash(go test)") == 1
    assert res_idempotent["permissions"]["deny"].count("Bash(go test ./...)") == 1

    # 3. Test defensive error handling
    # Missing settings.json: return False and do not create empty stub
    empty_root = tmp_path / 'empty_project'
    empty_root.mkdir()
    assert configure_claude_settings(empty_root, 'go') is False
    assert not (empty_root / '.claude' / 'settings.json').exists()

    # Malformed settings.json: return False and preserve file content untouched
    malformed_root = tmp_path / 'malformed_project'
    malformed_claude = malformed_root / '.claude'
    malformed_claude.mkdir(parents=True)
    malformed_file = malformed_claude / 'settings.json'
    invalid_content = '{"permissions": {invalid_json: true,'
    malformed_file.write_text(invalid_content, encoding='utf-8')
    assert configure_claude_settings(malformed_root, 'go') is False
    assert malformed_file.read_text(encoding='utf-8') == invalid_content

def test_check_closing_refs():
    # 1. Valid single closing reference in ## Linked Issue
    body_single = "## Summary\n\nImplements core logic.\n\n## Linked Issue\n\nCloses #29\n"
    is_valid, violations = validate_pr_closing_refs("feat: core logic", body_single)
    assert is_valid is True
    assert violations == []

    # 2. Valid multiple closing references in ## Linked Issue
    body_multiple = "## Summary\n\nFixes both items.\n\n## Linked Issue\n\nCloses #30\nCloses #43\n"
    is_valid, violations = validate_pr_closing_refs("feat: multi-fix", body_multiple)
    assert is_valid is True
    assert violations == []

    # 3. Valid non-closing mentions outside ## Linked Issue
    body_mentions = (
        "## Summary\n\n"
        "Part of #10, see #20, addresses #30, and relates to #40.\n\n"
        "## Linked Issue\n\n"
        "Closes #29\n"
    )
    is_valid, violations = validate_pr_closing_refs("feat: mentions", body_mentions)
    assert is_valid is True
    assert violations == []

    # 4. Closing reference in PR title -> FAIL
    is_valid, violations = validate_pr_closing_refs("fix: resolves #123", body_single)
    assert is_valid is False
    assert any("found in PR title" in v for v in violations)

    # 5. Stray closing reference in ## Summary (negation trap) -> FAIL
    body_negation = (
        "## Summary\n\n"
        "This implements part 1 but does not close #123.\n\n"
        "## Linked Issue\n\n"
        "Closes #29\n"
    )
    is_valid, violations = validate_pr_closing_refs("feat: part 1", body_negation)
    assert is_valid is False
    assert any("Stray closing reference" in v and "negation" in v for v in violations)

    # 6. Missing ## Linked Issue section -> FAIL unless allow_no_issue=True
    body_missing_section = "## Summary\n\nNo linked issue section anywhere.\n"
    is_valid, violations = validate_pr_closing_refs("feat: no section", body_missing_section, allow_no_issue=False)
    assert is_valid is False
    assert any("Missing '## Linked Issue' section" in v for v in violations)

    is_valid, violations = validate_pr_closing_refs("feat: no section", body_missing_section, allow_no_issue=True)
    assert is_valid is True
    assert violations == []

    # 7. Stray reference with allow_no_issue=True still FAILS
    body_stray_with_allow = "## Summary\n\nDoes not close #123.\n"
    is_valid, violations = validate_pr_closing_refs("feat: override", body_stray_with_allow, allow_no_issue=True)
    assert is_valid is False
    assert any("Stray closing reference" in v for v in violations)

    # 8. Unpopulated placeholder -> FAIL when issue required
    body_placeholder = "## Summary\n\nDesc.\n\n## Linked Issue\n\nCloses #<issue-number>\n"
    is_valid, violations = validate_pr_closing_refs("feat: placeholder", body_placeholder, allow_no_issue=False)
    assert is_valid is False
    assert any("unpopulated placeholder" in v for v in violations)

    # 9. Verify .github/PULL_REQUEST_TEMPLATE.md preserves non-numeric placeholder
    root_dir = Path(__file__).parent.parent
    pr_template = (root_dir / '.github' / 'PULL_REQUEST_TEMPLATE.md').read_text(encoding='utf-8')
    assert "Closes #<issue-number>" in pr_template
    assert not re.search(r'Closes #\d+', pr_template), "PR template should never contain a real numeric issue number"

    # 10. Closing references inside fenced code blocks do NOT count as strays
    body_fenced_code = (
        "## Summary\n\n"
        "Here is an example:\n"
        "```markdown\n"
        "Closes #123\n"
        "Fixes #456\n"
        "```\n\n"
        "## Linked Issue\n\n"
        "Closes #29\n"
    )
    is_valid, violations = validate_pr_closing_refs("docs: update rules", body_fenced_code)
    assert is_valid is True
    assert violations == []

    # 11. Closing references inside inline code spans do NOT count as strays
    body_inline_code = (
        "## Summary\n\n"
        "Be sure to put `Closes #123` or `Fixes #456` in the linked issue section.\n\n"
        "## Linked Issue\n\n"
        "Closes #29\n"
    )
    is_valid, violations = validate_pr_closing_refs("docs: update rules", body_inline_code)
    assert is_valid is True
    assert violations == []

    # 12. Closing references inside blockquotes and <details> blocks ARE caught as strays
    # (GitHub parses both as standard markdown, so they would trigger accidental closure)
    body_quote = (
        "## Summary\n\n"
        "> Quote discussing Fixes #123\n\n"
        "## Linked Issue\n\n"
        "Closes #29\n"
    )
    is_valid, violations = validate_pr_closing_refs("docs: quote test", body_quote)
    assert is_valid is False
    assert any("Stray closing reference 'Fixes #123'" in v for v in violations)

    body_details = (
        "## Summary\n\n"
        "<details open>\n"
        "<summary>Release notes</summary>\n"
        "- Fixes #789\n"
        "</details>\n\n"
        "## Linked Issue\n\n"
        "Closes #29\n"
    )
    is_valid, violations = validate_pr_closing_refs("docs: details test", body_details)
    assert is_valid is False
    assert any("Stray closing reference 'Fixes #789'" in v for v in violations)

    # 13. Closing references wrapped in code spans inside ## Linked Issue fail as non-closing
    # (GitHub ignores backticks/fences, so it would fail to link/close the issue on merge)
    body_code_linked = (
        "## Summary\n\n"
        "Implements feature.\n\n"
        "## Linked Issue\n\n"
        "`Closes #29`\n"
    )
    is_valid, violations = validate_pr_closing_refs("feat: code linked", body_code_linked)
    assert is_valid is False
    assert any("does not contain a valid closing reference" in v for v in violations)

    # 14. Automated bot PRs (e.g. dependabot[bot]) are exempted from checks
    body_bot = (
        "Bumps dependency from 1.0 to 2.0\n\n"
        "Changelog:\n"
        "Fixes #555 in upstream repo\n"
    )
    is_valid, violations = validate_pr_closing_refs("bump dep", body_bot, actor="dependabot[bot]")
    assert is_valid is True
    assert violations == []

    is_valid, violations = validate_pr_closing_refs("bump dep", body_bot, is_bot=True)
    assert is_valid is True
    assert violations == []

    # 15. Verify .github/workflows/issue-link-check.yml uses actions/checkout@v7
    issue_link_workflow = (root_dir / '.github' / 'workflows' / 'issue-link-check.yml').read_text(encoding='utf-8')
    assert "uses: actions/checkout@v7" in issue_link_workflow

def test_unit_testing_skill_fail_first_gate():
    root_dir = Path(__file__).parent.parent
    skill_content = (root_dir / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').read_text(encoding='utf-8')

    # Assert directive heading exists (without brittle section numbering prefix)
    assert "Fail-First Verification Gate (TDD Empirical Evidence)" in skill_content

    # Assert failure observation and citation mandate
    assert "cite the exact failing assertion output" in skill_content
    assert "terminal snippet showing the red failure" in skill_content

    # Assert mutate-to-confirm fallback and reversion gate
    assert "mutate or temporarily disable the new logic" in skill_content
    assert "Mutation Reversion & Clean Pass Gate" in skill_content
    assert "revert the intentional mutation immediately" in skill_content

    # Assert refactoring invariant baseline rule
    assert "For Refactoring" in skill_content
    assert "invariant baseline" in skill_content

    # Assert PR description logging mandate
    assert "Durable Citation in Pull Request" in skill_content
    assert "PR description" in skill_content

    # Assert docs/TEMPLATE_GUIDE.md Pattern 5 & skill table alignment
    guide_content = (root_dir / 'docs' / 'TEMPLATE_GUIDE.md').read_text(encoding='utf-8')
    assert "Empirical Test-Driven Verification Gate" in guide_content
    assert "reproduction test must be observed and cited failing red" in guide_content
    assert "fail-first verification gates" in guide_content

def test_ruleset_validator_supports_same_named_skip_jobs(tmp_path):
    """Verify that extract_workflow_job_contexts cleanly supports the filter + same-named skip-job pattern."""
    wf_file = tmp_path / 'heavy-ci.yml'
    wf_file.write_text(
        "jobs:\n"
        "  filter:\n"
        "    runs-on: ubuntu-latest\n"
        "  build-and-test:\n"
        "    needs: filter\n"
        "    if: needs.filter.outputs.code == 'true'\n"
        "    name: CI / Build and Test\n"
        "  build-and-test-skip:\n"
        "    needs: filter\n"
        "    if: needs.filter.outputs.code != 'true'\n"
        "    name: CI / Build and Test\n",
        encoding='utf-8'
    )
    valid_contexts = extract_workflow_job_contexts(tmp_path)
    assert "CI / Build and Test" in valid_contexts
    assert "filter" in valid_contexts

def test_branch_protection_docs_mentions_path_filter_deadlock():
    """Verify that docs/BRANCH_PROTECTION.md explains the path-filter deadlock risk and failure caveats."""
    doc = Path(__file__).parent.parent / 'docs' / 'BRANCH_PROTECTION.md'
    content = doc.read_text(encoding='utf-8')
    assert "Path-Filtered CI Deadlock" in content
    assert "skip-job pattern" in content
    assert "if the filter job itself fails" in content

def test_check_pr_scope_logic():
    """Verify check_pr_scope logic across branches, titles, labels, and file counts."""
    from check_pr_scope import validate_pr_scope

    # 1. Non-bugfix branch and title: always passes regardless of file count
    assert validate_pr_scope(branch="feat/new-feature", title="feat: add feature", labels=[], changed_count=50) == (True, "Non-bugfix PR: scope sprawl check not applicable.")
    assert validate_pr_scope(branch="chore/cleanup", title="chore: clean repo", labels=[], changed_count=25) == (True, "Non-bugfix PR: scope sprawl check not applicable.")

    # 2. Bot PR immunity (Dependabot / Renovate)
    assert validate_pr_scope(branch="dependabot/pip/pytest-9.0", title="build(deps): bump pytest", labels=[], changed_count=30) == (True, "Non-bugfix PR: scope sprawl check not applicable.")
    assert validate_pr_scope(branch="renovate/actions", title="chore(deps): update actions", labels=[], changed_count=20) == (True, "Non-bugfix PR: scope sprawl check not applicable.")

    # 3. Bugfix branch or title within 10-file threshold: passes
    assert validate_pr_scope(branch="fix/typo", title="docs: fix typo", labels=[], changed_count=5)[0] is True
    assert validate_pr_scope(branch="bugfix/issue-12", title="fix(ci): fix yaml error", labels=[], changed_count=10)[0] is True
    assert validate_pr_scope(branch="feature/something", title="fix: one line bug", labels=[], changed_count=1)[0] is True

    # 4. Bugfix exceeding 10 files without bypass label: fails
    ok, msg = validate_pr_scope(branch="fix/big-fix", title="fix: bug", labels=[], changed_count=11)
    assert ok is False
    assert "modifies 11 files (limit is 10)" in msg
    assert "bypass-sprawl" in msg

    # 5. Bugfix exceeding 10 files with bypass-sprawl label: passes
    ok, msg = validate_pr_scope(branch="fix/big-fix", title="fix: bug", labels=["bypass-sprawl"], changed_count=25)
    assert ok is True
    assert "bypassed via 'bypass-sprawl' label" in msg

    # 6. Configurable max-files
    ok, msg = validate_pr_scope(branch="fix/custom", title="fix: bug", labels=[], changed_count=5, max_files=3)
    assert ok is False
    assert "limit is 3" in msg

def test_coding_standards_skill_scope_sprawl_rule():
    """Verify coding-standards/SKILL.md defines Directive 5 (Scope Sprawl & Anti-Churn Guardrails)."""
    skill = Path(__file__).parent.parent / '.agents' / 'skills' / 'coding-standards' / 'SKILL.md'
    content = skill.read_text(encoding='utf-8')
    assert "Scope Sprawl & Anti-Churn Guardrails" in content
    assert "MUST NOT modify more than 10 files" in content
    assert "bypass-sprawl" in content

# --- Community health & editor baseline files (issue #53) -------------------

# Sample filenames representing each stack in bootstrap_template.SUPPORTED_LANGUAGES.
# Keyed by language so a newly supported language without an .editorconfig rule fails loudly.
LANGUAGE_SAMPLE_FILES = {
    'generic': 'notes.txt',
    'go': 'main.go',
    'python': 'app.py',
    'rust': 'lib.rs',
    'java': 'Service.java',
    'node': 'index.ts',
    'cpp': 'engine.cpp',
    'liferay': 'client-extension.yaml',
}

def _expand_editorconfig_globs(pattern: str) -> list:
    """Expand an EditorConfig brace list ({py,pyi}) into plain fnmatch globs."""
    match = re.search(r'\{([^{}]*)\}', pattern)
    if not match:
        return [pattern]
    expanded = []
    for option in match.group(1).split(','):
        expanded.extend(
            _expand_editorconfig_globs(pattern[:match.start()] + option.strip() + pattern[match.end():])
        )
    return expanded

def _parse_editorconfig(content: str) -> tuple:
    """Parse .editorconfig into (preamble properties, ordered [(section glob, properties)])."""
    preamble = {}
    sections = []
    current = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = (line[1:-1], {})
            sections.append(current)
            continue
        if '=' not in line:
            continue
        key, value = (part.strip() for part in line.split('=', 1))
        target = current[1] if current else preamble
        target[key] = value
    return preamble, sections

def _matching_section_globs(sections: list, filename: str) -> list:
    return [
        glob_pattern for glob_pattern, _ in sections
        if any(fnmatch.fnmatch(filename, g) for g in _expand_editorconfig_globs(glob_pattern))
    ]

def _resolve_editorconfig(sections: list, filename: str) -> dict:
    """Resolve effective EditorConfig properties for a filename (later sections win)."""
    resolved = {}
    for glob_pattern, properties in sections:
        if any(fnmatch.fnmatch(filename, g) for g in _expand_editorconfig_globs(glob_pattern)):
            resolved.update(properties)
    return resolved

def test_community_health_files_exist_as_adopter_stubs():
    """All five community health files ship, each marked as an adopter-customisable stub."""
    root_dir = Path(__file__).parent.parent

    for rel_path in COMMUNITY_HEALTH_FILES:
        assert (root_dir / rel_path).exists(), f"Missing community health file: {rel_path}"

    conduct = (root_dir / 'CODE_OF_CONDUCT.md').read_text(encoding='utf-8')
    assert 'Contributor Covenant' in conduct
    assert CONDUCT_EMAIL_PLACEHOLDER in conduct, "Code of Conduct must keep a substitutable contact placeholder"

    changelog = (root_dir / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert 'Keep a Changelog' in changelog
    assert 'Semantic Versioning' in changelog
    assert '## [Unreleased]' in changelog

    codeowners = (root_dir / '.github' / 'CODEOWNERS').read_text(encoding='utf-8')
    active_rules = [line for line in codeowners.splitlines() if line.strip() and not line.strip().startswith('#')]
    assert not active_rules, f"CODEOWNERS must ship fully commented out, found active rules: {active_rules}"
    assert 'require_code_owner_review' in codeowners, "CODEOWNERS stub must explain the ruleset interaction"
    assert OWNER_PLACEHOLDER in codeowners

    config = yaml.safe_load((root_dir / '.github' / 'ISSUE_TEMPLATE' / 'config.yml').read_text(encoding='utf-8'))
    assert config.get('blank_issues_enabled') is False
    contact_links = config.get('contact_links')
    assert isinstance(contact_links, list) and contact_links, "config.yml must define contact_links"
    for link in contact_links:
        assert {'name', 'url', 'about'} <= set(link), f"Incomplete contact link: {link}"
        assert link['url'].startswith('https://'), f"Contact link must be https: {link['url']}"

def test_editorconfig_baseline_covers_supported_languages():
    """.editorconfig defines the shared baseline plus an indent rule per supported language."""
    root_dir = Path(__file__).parent.parent
    preamble, sections = _parse_editorconfig((root_dir / '.editorconfig').read_text(encoding='utf-8'))

    assert preamble.get('root') == 'true', ".editorconfig must declare root = true"

    universal = _resolve_editorconfig(sections, 'notes.txt')
    assert universal.get('charset') == 'utf-8'
    assert universal.get('end_of_line') == 'lf'
    assert universal.get('insert_final_newline') == 'true'
    assert universal.get('trim_trailing_whitespace') == 'true'

    assert set(LANGUAGE_SAMPLE_FILES) == set(SUPPORTED_LANGUAGES), (
        "LANGUAGE_SAMPLE_FILES drifted from bootstrap_template.SUPPORTED_LANGUAGES: "
        f"only in map: {set(LANGUAGE_SAMPLE_FILES) - set(SUPPORTED_LANGUAGES)}; "
        f"only supported: {set(SUPPORTED_LANGUAGES) - set(LANGUAGE_SAMPLE_FILES)}"
    )

    for language, sample_file in LANGUAGE_SAMPLE_FILES.items():
        matched = _matching_section_globs(sections, sample_file)
        if language == 'generic':
            assert matched, "generic stacks must at least inherit the universal [*] section"
            continue
        assert [g for g in matched if g != '*'], (
            f"No language-specific .editorconfig section matches {sample_file} ({language})"
        )

    assert _resolve_editorconfig(sections, 'main.go').get('indent_style') == 'tab', "Go must use tabs (gofmt)"
    assert _resolve_editorconfig(sections, 'app.py').get('indent_size') == '4', "Python must use 4 spaces (PEP 8)"

    # The pre-commit trailing-whitespace hook trims Markdown too, so .editorconfig must not
    # disagree with it: an editor preserving Markdown hard breaks would fight the hook.
    assert _resolve_editorconfig(sections, 'README.md').get('trim_trailing_whitespace') == 'true'

def test_non_markdown_community_files_are_not_timestamped(tmp_path):
    """.editorconfig, CODEOWNERS and config.yml must never receive Markdown timestamp footers."""
    non_markdown = [f for f in COMMUNITY_HEALTH_FILES if not f.endswith('.md')]
    assert non_markdown, "Expected non-Markdown community health files"

    for rel_path in non_markdown:
        assert rel_path not in EXTRA_DOC_FILES, f"{rel_path} must not be treated as a timestamped doc"

    original = {}
    for rel_path in non_markdown:
        target = tmp_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# stub content\n', encoding='utf-8')
        original[rel_path] = target.read_bytes()

    append_timestamps(tmp_path)

    for rel_path in non_markdown:
        assert (tmp_path / rel_path).read_bytes() == original[rel_path], (
            f"{rel_path} was rewritten by append_timestamps"
        )

    root_dir = Path(__file__).parent.parent
    for rel_path in non_markdown:
        assert 'Last Reviewed' not in (root_dir / rel_path).read_text(encoding='utf-8')

def test_community_health_files_documented_in_readme_tree():
    """README.md's repository-structure tree must list the community health files."""
    root_dir = Path(__file__).parent.parent
    readme_content = (root_dir / 'README.md').read_text(encoding='utf-8')
    tree_match = re.search(r'## Repository Structure\s*```text(.*?)```', readme_content, re.DOTALL)
    assert tree_match, "Could not locate the repository structure tree in README.md"
    tree = tree_match.group(1)

    for rel_path in COMMUNITY_HEALTH_FILES:
        assert Path(rel_path).name in tree, f"README.md tree missing '{rel_path}'"

    # Guard the sibling drift test's anchor: the skills block must stay between these markers.
    assert re.search(r'├── \.agents/skills/.*?(?=├── scripts/)', readme_content, re.DOTALL)

def test_bootstrap_substitutes_community_health_placeholders(tmp_path):
    """Bootstrap replaces owner/email/project placeholders and reports unresolved leftovers."""
    def seed(root: Path):
        (root / '.github' / 'ISSUE_TEMPLATE').mkdir(parents=True, exist_ok=True)
        (root / 'CODE_OF_CONDUCT.md').write_text(
            f"Report conduct concerns to {CONDUCT_EMAIL_PLACEHOLDER}.\n", encoding='utf-8')
        (root / 'CHANGELOG.md').write_text(
            f"# Changelog for {TEMPLATE_PROJECT_NAME}\n", encoding='utf-8')
        (root / '.editorconfig').write_text("root = true\n", encoding='utf-8')
        (root / '.github' / 'CODEOWNERS').write_text(
            f"# * @{OWNER_PLACEHOLDER}\n", encoding='utf-8')
        (root / '.github' / 'ISSUE_TEMPLATE' / 'config.yml').write_text(
            f"url: https://github.com/{OWNER_PLACEHOLDER}/{TEMPLATE_PROJECT_NAME}/blob/main/CONTRIBUTING.md\n",
            encoding='utf-8')

    resolved_root = tmp_path / 'resolved'
    resolved_root.mkdir()
    seed(resolved_root)

    unresolved = substitute_community_health_placeholders(
        resolved_root,
        project_name='my-awesome-service',
        repo_owner='acme-org',
        conduct_email='conduct@acme.example',
    )
    assert unresolved == [], f"Expected no unresolved placeholders, got {unresolved}"

    conduct = (resolved_root / 'CODE_OF_CONDUCT.md').read_text(encoding='utf-8')
    assert 'conduct@acme.example' in conduct and CONDUCT_EMAIL_PLACEHOLDER not in conduct

    changelog = (resolved_root / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert 'my-awesome-service' in changelog and TEMPLATE_PROJECT_NAME not in changelog

    codeowners = (resolved_root / '.github' / 'CODEOWNERS').read_text(encoding='utf-8')
    assert '@acme-org' in codeowners and OWNER_PLACEHOLDER not in codeowners

    config_text = (resolved_root / '.github' / 'ISSUE_TEMPLATE' / 'config.yml').read_text(encoding='utf-8')
    assert 'https://github.com/acme-org/my-awesome-service/blob/main/CONTRIBUTING.md' in config_text

    # .editorconfig carries no placeholders and must be left byte-identical.
    assert (resolved_root / '.editorconfig').read_text(encoding='utf-8') == "root = true\n"

    # Without owner/email arguments the placeholders survive and are reported for manual editing.
    partial_root = tmp_path / 'partial'
    partial_root.mkdir()
    seed(partial_root)

    unresolved = substitute_community_health_placeholders(partial_root, project_name='my-awesome-service')
    assert unresolved == sorted(['CODE_OF_CONDUCT.md', '.github/CODEOWNERS', '.github/ISSUE_TEMPLATE/config.yml'])
    assert CONDUCT_EMAIL_PLACEHOLDER in (partial_root / 'CODE_OF_CONDUCT.md').read_text(encoding='utf-8')
    assert 'my-awesome-service' in (partial_root / 'CHANGELOG.md').read_text(encoding='utf-8')

def test_bootstrap_placeholder_substitution_tolerates_missing_files(tmp_path):
    """Substitution must not fail when a downstream repo has deleted a community health file."""
    assert substitute_community_health_placeholders(tmp_path, project_name='empty-repo') == []
def test_check_commit_attribution_validation_logic():
    """Verify the attribution heuristic accepts noreply/allowlisted emails and rejects unknown ones."""
    from check_commit_attribution import validate_commit_attribution

    # 1. GitHub noreply addresses always attribute (with and without the numeric ID prefix)
    assert validate_commit_attribution("octocat@users.noreply.github.com", [])[0] is True
    assert validate_commit_attribution("12345+octocat@users.noreply.github.com", [])[0] is True

    # 2. Matching is case-insensitive and tolerates surrounding whitespace
    assert validate_commit_attribution("  OctoCat@Users.NoReply.GitHub.com  ", [])[0] is True

    # 3. Lookalike domains must not slip through a naive substring match
    assert validate_commit_attribution("octocat@users.noreply.github.com.example.org", [])[0] is False

    # 4. Unset email fails with configuration remediation
    ok, message = validate_commit_attribution("", [])
    assert ok is False
    assert "user.email" in message

    # 5. Custom domain fails when it is not allowlisted
    assert validate_commit_attribution("dev@example.com", [])[0] is False

    # 6. Custom domain passes once allowlisted (case-insensitive, whitespace tolerant)
    assert validate_commit_attribution("dev@example.com", ["dev@example.com"])[0] is True
    assert validate_commit_attribution("Dev@Example.com", [" dev@example.com "])[0] is True

def test_check_commit_attribution_allowlist_parsing():
    """Verify allowlist entries split on commas/whitespace and normalise to lowercase."""
    from check_commit_attribution import parse_allowlist_entries

    assert parse_allowlist_entries(["a@x.com, b@y.com"]) == ["a@x.com", "b@y.com"]
    assert parse_allowlist_entries(["a@x.com b@y.com", "c@z.com"]) == ["a@x.com", "b@y.com", "c@z.com"]
    assert parse_allowlist_entries(["A@X.com"]) == ["a@x.com"]
    assert parse_allowlist_entries(["", "   ", ","]) == []
    assert parse_allowlist_entries(None) == []

def test_check_commit_attribution_failure_message_is_heuristic_aware():
    """The failure message must present itself as a heuristic, not a verdict that the email is wrong."""
    from check_commit_attribution import validate_commit_attribution, ALLOWLIST_CONFIG_KEY

    ok, message = validate_commit_attribution("dev@verified-custom-domain.example", [])
    assert ok is False

    lowered = message.lower()
    # States plainly that this is a heuristic and that a verified address can legitimately fail it
    assert "heuristic" in lowered
    assert "verified" in lowered
    # Offers both escape hatches: the noreply address and the allowlist
    assert "users.noreply.github.com" in lowered
    assert ALLOWLIST_CONFIG_KEY in message

def test_check_commit_attribution_ci_environment_detection():
    """The guard protects local commit creation, so it stands down inside CI runners."""
    from check_commit_attribution import is_continuous_integration_environment

    assert is_continuous_integration_environment({"CI": "true"}) is True
    assert is_continuous_integration_environment({"GITHUB_ACTIONS": "true"}) is True
    assert is_continuous_integration_environment({"CI": "false"}) is False
    assert is_continuous_integration_environment({}) is False

def test_check_commit_attribution_cli_exit_codes():
    """Verify the CLI contract: exit 0 when attributable, exit 1 with guidance when not."""
    script = Path(__file__).parent.parent / 'scripts' / 'check_commit_attribution.py'

    attributable = subprocess.run(
        [sys.executable, str(script), '--email', 'octocat@users.noreply.github.com'],
        capture_output=True, text=True
    )
    assert attributable.returncode == 0

    unattributable = subprocess.run(
        [sys.executable, str(script), '--email', 'dev@example.com'],
        capture_output=True, text=True
    )
    assert unattributable.returncode == 1
    assert "heuristic" in (unattributable.stdout + unattributable.stderr).lower()

    allowlisted = subprocess.run(
        [sys.executable, str(script), '--email', 'dev@example.com', '--allowlist', 'dev@example.com'],
        capture_output=True, text=True
    )
    assert allowlisted.returncode == 0

def test_pre_commit_config_registers_commit_attribution_hook():
    """Verify the attribution guard runs as a local pre-commit hook on every commit."""
    config = Path(__file__).parent.parent / '.pre-commit-config.yaml'
    data = yaml.safe_load(config.read_text(encoding='utf-8'))

    local_hooks = [hook for repo in data['repos'] if repo['repo'] == 'local' for hook in repo['hooks']]
    attribution_hook = next((hook for hook in local_hooks if hook['id'] == 'check-commit-attribution'), None)

    assert attribution_hook is not None, "check-commit-attribution hook is not registered in .pre-commit-config.yaml"
    assert 'scripts/check_commit_attribution.py' in attribution_hook['entry']
    # The identity being checked is repository-wide, not tied to any staged file
    assert attribution_hook.get('pass_filenames') is False
    assert attribution_hook.get('always_run') is True

def test_shipped_rulesets_omit_unattributed_approval_rule():
    """docs/BRANCH_PROTECTION.md states neither shipped ruleset enables this rule -- keep that true."""
    ruleset_dir = Path(__file__).parent.parent / '.github' / 'rulesets'
    ruleset_files = sorted(ruleset_dir.glob('*.json'))
    assert ruleset_files, "No rulesets found to verify"

    for ruleset_file in ruleset_files:
        assert 'require_extra_approval_for_unattributed_changes' not in ruleset_file.read_text(encoding='utf-8'), (
            f"{ruleset_file.name} now enables require_extra_approval_for_unattributed_changes; "
            "docs/BRANCH_PROTECTION.md must be updated to match."
        )

def test_branch_protection_docs_covers_unattributed_changes_trap():
    """Verify the unattributed-changes trap sits alongside the existing solo-maintainer review guidance."""
    doc = Path(__file__).parent.parent / 'docs' / 'BRANCH_PROTECTION.md'
    content = doc.read_text(encoding='utf-8')
    lowered = content.lower()

    assert "require_extra_approval_for_unattributed_changes" in content
    # Must be accurate about where the trap actually comes from
    assert "neither ruleset in" in lowered
    assert "org-level" in lowered
    # Must point at the local guard as the mitigation
    assert "scripts/check_commit_attribution.py" in content

def test_contributing_documents_commit_attribution():
    """Verify CONTRIBUTING.md tells contributors how to satisfy or allowlist the attribution guard."""
    content = (Path(__file__).parent.parent / 'CONTRIBUTING.md').read_text(encoding='utf-8')
    assert "Commit Attribution" in content
    assert "scripts/check_commit_attribution.py" in content
    assert "user.attributableEmails" in content
    assert "users.noreply.github.com" in content
def test_agent_state_seed_and_bootstrap(tmp_path, capsys):
    """Verify the tracked .agent-state.md seed exists and bootstrap creates it in a fresh clone."""
    root_dir = Path(__file__).parent.parent
    seed_file = root_dir / AGENT_STATE_SEED_RELPATH

    # 1. Seed template must be tracked by git while .agent-state.md itself stays ignored
    assert seed_file.exists(), f"Missing tracked scratchpad seed template: {AGENT_STATE_SEED_RELPATH}"

    res_seed = subprocess.run(
        ['git', 'check-ignore', AGENT_STATE_SEED_RELPATH.as_posix()],
        cwd=root_dir, capture_output=True, text=True
    )
    assert res_seed.returncode == 1, f"Expected {AGENT_STATE_SEED_RELPATH} NOT to be ignored by git"

    res_state = subprocess.run(
        ['git', 'check-ignore', '.agent-state.md'],
        cwd=root_dir, capture_output=True, text=True
    )
    assert res_state.returncode == 0, "Expected .agent-state.md to remain ignored by git"

    seed_content = seed_file.read_text(encoding='utf-8')
    # github-workflow/SKILL.md rule 4: tech debt is tracked solely as GitHub issues
    assert "Technical Debt Registry" not in seed_content, "Seed must not carry a second tech-debt registry"
    assert TEMPLATE_PROJECT_NAME in seed_content, "Seed must carry the placeholder project name for substitution"

    # 2. Fresh clone case: no .agent-state.md present, bootstrap must create and customize it
    dummy_root = tmp_path / 'project'
    (dummy_root / AGENT_STATE_SEED_RELPATH.parent).mkdir(parents=True)
    (dummy_root / AGENT_STATE_SEED_RELPATH).write_text(seed_content, encoding='utf-8')
    agent_state = dummy_root / '.agent-state.md'
    assert not agent_state.exists()

    assert ensure_agent_state_scratchpad(dummy_root, 'my-new-project') is True
    assert agent_state.exists(), "Bootstrap must create .agent-state.md when it is absent"

    created = agent_state.read_text(encoding='utf-8')
    assert 'my-new-project' in created
    assert TEMPLATE_PROJECT_NAME not in created

    # Step must report a real outcome, never skip silently
    out_created = capsys.readouterr().out
    assert "Created .agent-state.md" in out_created
    assert "Customized .agent-state.md" in out_created

    # 3. Idempotency: an existing scratchpad is customized in place, never overwritten
    agent_state.write_text(
        "# Existing Scratchpad\n\n- **Repository**: `ai-agent-template`\n- In-flight work preserved.\n",
        encoding='utf-8'
    )
    assert ensure_agent_state_scratchpad(dummy_root, 'my-new-project') is True
    preserved = agent_state.read_text(encoding='utf-8')
    assert "In-flight work preserved." in preserved
    assert "- **Repository**: `my-new-project`" in preserved

    out_existing = capsys.readouterr().out
    assert "Created .agent-state.md" not in out_existing
    assert "Customized .agent-state.md" in out_existing

    # 4. Missing seed template must report failure rather than a silent no-op success
    bare_root = tmp_path / 'bare_project'
    bare_root.mkdir()
    assert ensure_agent_state_scratchpad(bare_root, 'my-new-project') is False
    assert not (bare_root / '.agent-state.md').exists()
def test_github_workflow_skill_pr_review_feedback_loop():
    """Verify github-workflow/SKILL.md defines the post-`gh pr create` review feedback loop."""
    root_dir = Path(__file__).parent.parent
    skill = (root_dir / '.agents' / 'skills' / 'github-workflow' / 'SKILL.md').read_text(encoding='utf-8')

    # 1. Directive heading exists (without brittle section numbering prefix)
    assert "PR Review & CI Feedback Loop" in skill

    # 2. Feedback is pulled by the agent, never requested from the human. Retrieval takes
    #    TWO calls: `gh pr view --json` exposes no field carrying inline review comments
    #    (`comments` is the conversation timeline, `reviews` is review summaries), so the
    #    file/line-anchored threads the rule acts on are only reachable via `gh api`.
    assert "gh pr view <number> --json reviews,comments,statusCheckRollup" in skill
    assert "gh api 'repos/{owner}/{repo}/pulls/<number>/comments'" in skill
    assert "Never ask the user to paste review comments" in skill

    # 2b. The reason two calls are needed is recorded in the rule itself, so a later edit
    #     cannot "simplify" it back to one and leave "map each comment to file and line"
    #     unsatisfiable again.
    assert "two calls, not one" in skill
    assert 'Do not "simplify" this back to a single command' in skill
    assert "no field for inline review comments" in skill
    assert "`path`, `line` and `body`" in skill
    assert "bare `gh pr view` resolves the PR from the currently checked-out branch" in skill

    # 3. Comment-by-comment closure protocol
    assert "Map each comment to the specific file and line" in skill
    assert "report back which comments were addressed and how" in skill
    assert "neither actioned nor answered is an open thread" in skill

    # 4. CI status retrieval consolidated into the same call, drill-down + cleanup retained
    assert "statusCheckRollup" in skill
    assert "gh run view <run-id> --log" in skill
    assert "gh run delete <run-id>" in skill

    # 5. Boundary with human-in-the-loop: pushing fixes is routine, resolving threads is not
    assert "human-in-the-loop/SKILL.md" in skill
    assert "Resolving a reviewer's thread on their behalf" in skill

    # 6. Routing tables describe the widened skill scope (doc drift guard)
    agents_content = (root_dir / 'AGENTS.md').read_text(encoding='utf-8')
    guide_content = (root_dir / 'docs' / 'TEMPLATE_GUIDE.md').read_text(encoding='utf-8')
    assert "PR review feedback loop" in agents_content
    assert "PR review feedback loop" in guide_content
    assert "pulls/<number>/comments" in agents_content
    assert "pulls/<number>/comments" in guide_content
