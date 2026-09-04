"""
test_template_scripts.py - Unit Test Suite for Template Automation Scripts

Tests append_timestamps.py, check_docs_review.py, bootstrap_template.py, and gh_issue_sync.py.
"""

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
from check_docs_review import check_docs, parse_date
from bootstrap_template import configure_language_profile, clean_template_meta_docs, get_default_topics, ensure_claude_skills_symlink, configure_claude_settings
from gh_issue_sync import sync_issues
from setup_branch_protection import apply_branch_protection, validate_ruleset_file
from check_provider_redirects import check_redirects, MAX_REDIRECT_LINES, REDIRECT_FILES

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
