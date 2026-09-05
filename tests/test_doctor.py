"""
test_doctor.py - Post-Bootstrap Verification Suite

Covers scripts/doctor.py: the check that fails loudly when a template placeholder
survives bootstrap, when the .claude/skills auto-discovery symlink did not
materialise as a directory, or when the agent scratchpad was never seeded (#56).
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# Add scripts directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from doctor import (
    ADOPTER_MODE,
    TEMPLATE_MODE,
    format_findings,
    run_doctor,
)

REPO_ROOT = Path(__file__).parent.parent
DOCTOR_SCRIPT = REPO_ROOT / 'scripts' / 'doctor.py'

def make_bootstrapped_tree(tmp_path: Path) -> Path:
    """Build the minimal tree a correctly bootstrapped project is expected to have."""
    (tmp_path / '.agents' / 'skills').mkdir(parents=True)
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills', target_is_directory=True)
    (tmp_path / '.agent-state.md').write_text("# Scratchpad\n", encoding='utf-8')
    (tmp_path / 'AGENTS.md').write_text(
        "# Rules\n\nPrimary Unit Testing Command: `pytest -v --tb=short`\n", encoding='utf-8')
    (tmp_path / 'README.md').write_text(
        "# acme-service\n\ngit clone https://github.com/acme/acme-service.git\n", encoding='utf-8')
    return tmp_path

def finding_paths(findings) -> set:
    return {finding.path for finding in findings}

# --- placeholder scanning ----------------------------------------------------

def test_clean_bootstrapped_tree_reports_no_findings(tmp_path):
    make_bootstrapped_tree(tmp_path)
    assert run_doctor(tmp_path, mode=ADOPTER_MODE) == []

def test_surviving_test_command_placeholder_is_reported_with_file_and_line(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'AGENTS.md').write_text(
        "# Rules\n\n### 5. Primary Unit Testing Command\n"
        "Primary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`\n", encoding='utf-8')

    findings = run_doctor(tmp_path, mode=ADOPTER_MODE)

    assert len(findings) == 1
    assert findings[0].path == 'AGENTS.md'
    assert findings[0].line == 4
    assert '<TEST_COMMAND_PLACEHOLDER>' in findings[0].detail

def test_your_org_clone_url_is_reported(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'README.md').write_text(
        "# Quickstart\n\ngit clone https://github.com/your-org/ai-agent-template.git\n",
        encoding='utf-8')

    findings = run_doctor(tmp_path, mode=ADOPTER_MODE)

    assert finding_paths(findings) == {'README.md'}
    assert 'your-org' in findings[0].detail

def test_every_occurrence_is_reported_not_just_the_first(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'CODE_OF_CONDUCT.md').write_text(
        "# Conduct\n\nReport to <CONDUCT_EMAIL_PLACEHOLDER>.\n"
        "Owned by <GITHUB_OWNER_PLACEHOLDER>.\n", encoding='utf-8')

    findings = run_doctor(tmp_path, mode=ADOPTER_MODE)

    assert [(f.path, f.line) for f in findings] == [
        ('CODE_OF_CONDUCT.md', 3),
        ('CODE_OF_CONDUCT.md', 4),
    ]

def test_default_project_name_placeholder_is_reported(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / '.agent-state.md').write_text(
        "# Scratchpad\n\n- **Repository**: `my-ai-project`\n", encoding='utf-8')

    findings = run_doctor(tmp_path, mode=ADOPTER_MODE)

    assert finding_paths(findings) == {'.agent-state.md'}

def test_binary_files_are_skipped_without_error(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'logo.png').write_bytes(b'\x89PNG\r\n\x1a\n\xff\xfe\x00your-org')

    assert run_doctor(tmp_path, mode=ADOPTER_MODE) == []

# --- structural checks -------------------------------------------------------

def test_claude_skills_materialised_as_regular_file_is_reported(tmp_path):
    make_bootstrapped_tree(tmp_path)
    skills_link = tmp_path / '.claude' / 'skills'
    skills_link.unlink()
    skills_link.write_text('../.agents/skills', encoding='utf-8')

    findings = run_doctor(tmp_path, mode=ADOPTER_MODE)

    assert finding_paths(findings) == {'.claude/skills'}
    assert 'core.symlinks' in findings[0].detail

def test_missing_claude_skills_link_is_reported(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / '.claude' / 'skills').unlink()

    assert finding_paths(run_doctor(tmp_path, mode=ADOPTER_MODE)) == {'.claude/skills'}

def test_missing_agent_state_scratchpad_is_reported(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / '.agent-state.md').unlink()

    findings = run_doctor(tmp_path, mode=ADOPTER_MODE)

    assert finding_paths(findings) == {'.agent-state.md'}

def test_template_mode_does_not_require_the_gitignored_scratchpad(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / '.agent-state.md').unlink()

    assert run_doctor(tmp_path, mode=TEMPLATE_MODE) == []

# --- template mode exemptions ------------------------------------------------

def test_template_mode_exempts_the_unbootstrapped_stubs(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'AGENTS.md').write_text(
        "Primary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`\n", encoding='utf-8')
    (tmp_path / 'CODE_OF_CONDUCT.md').write_text(
        "Report to <CONDUCT_EMAIL_PLACEHOLDER>.\n", encoding='utf-8')

    assert run_doctor(tmp_path, mode=TEMPLATE_MODE) == []
    assert len(run_doctor(tmp_path, mode=ADOPTER_MODE)) == 2

def test_template_mode_still_flags_placeholders_in_the_readme(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'README.md').write_text(
        "git clone https://github.com/your-org/ai-agent-template.git\n", encoding='utf-8')

    assert finding_paths(run_doctor(tmp_path, mode=TEMPLATE_MODE)) == {'README.md'}

# --- reporting and CLI -------------------------------------------------------

def test_format_findings_cites_every_file_and_line(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'README.md').write_text("a\nyour-org\n", encoding='utf-8')

    report = format_findings(run_doctor(tmp_path, mode=ADOPTER_MODE))

    assert 'README.md:2' in report

def test_cli_exits_non_zero_and_lists_the_offending_lines(tmp_path):
    make_bootstrapped_tree(tmp_path)
    (tmp_path / 'README.md').write_text("a\nyour-org\n", encoding='utf-8')

    result = subprocess.run(
        [sys.executable, str(DOCTOR_SCRIPT), '--dir', str(tmp_path)],
        capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert 'README.md:2' in result.stdout + result.stderr

def test_cli_exits_zero_on_a_clean_tree(tmp_path):
    make_bootstrapped_tree(tmp_path)

    result = subprocess.run(
        [sys.executable, str(DOCTOR_SCRIPT), '--dir', str(tmp_path)],
        capture_output=True, text=True, check=False)

    assert result.returncode == 0

def test_cli_rejects_an_unknown_mode(tmp_path):
    result = subprocess.run(
        [sys.executable, str(DOCTOR_SCRIPT), '--dir', str(tmp_path), '--mode', 'nonsense'],
        capture_output=True, text=True, check=False)

    assert result.returncode != 0

# --- the template repository itself must stay clean --------------------------

def test_template_repository_passes_the_doctor_in_template_mode():
    findings = run_doctor(REPO_ROOT, mode=TEMPLATE_MODE)
    assert findings == [], format_findings(findings)

def test_precommit_config_runs_the_doctor():
    config = yaml.safe_load((REPO_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8'))
    entries = [
        hook['entry']
        for repo in config['repos']
        for hook in repo.get('hooks', [])
        if hook.get('id') == 'doctor'
    ]
    assert entries, "no 'doctor' hook declared in .pre-commit-config.yaml"
    assert 'scripts/doctor.py' in entries[0]

def test_ci_workflow_runs_the_doctor():
    workflow = (REPO_ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    assert 'scripts/doctor.py' in workflow
