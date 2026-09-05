"""
test_bootstrap_cleanup.py - Bootstrap Mutation Safety & Scaffolding Cleanup Suite

Covers the bootstrap behaviours that must not fail silently:
- the seeded .agent-state.md footer is rewritten to the bootstrap date (#80),
- regex substitutions that match nothing abort instead of warning (#56),
- --dry-run previews every mutation without touching the working tree (#56),
- --clean-template scrubs the template's Python-only scaffolding (#55).
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add scripts directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import bootstrap_template
from bootstrap_template import (
    AGENT_STATE_SEED_RELPATH,
    DOCTOR_ADOPTER_MODE_ENTRY,
    DOCTOR_TEMPLATE_MODE_ENTRY,
    PRE_COMMIT_CONFIG_RELPATH,
    PYTHON_PACKAGE_MARKER_RELPATH,
    PYTHON_REQUIREMENTS_RELPATH,
    TEMPLATE_SELF_TEST_RELPATH,
    clean_python_scaffolding,
    configure_doctor_precommit_hook,
    configure_language_profile,
    configure_repository_seo,
    ensure_agent_state_scratchpad,
)
from check_docs_review import check_docs

REPO_ROOT = Path(__file__).parent.parent
TODAY = datetime.today().strftime('%Y-%m-%d')

STALE_SEED_TEXT = (
    "# Active AI Agent Work State (Ephemeral Scratchpad)\n\n"
    "- **Repository**: `ai-agent-template`\n\n"
    "<!-- markdownlint-disable MD049 -->\n"
    "---\n"
    "*Last Updated: 2020-01-01* | *Last Reviewed: 2020-01-01*\n"
)

def write_stale_seed(root_dir: Path) -> Path:
    """Seed a tree with an agent-state template whose footer is long expired."""
    seed_path = root_dir / AGENT_STATE_SEED_RELPATH
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(STALE_SEED_TEXT, encoding='utf-8')
    return seed_path

# --- #80: the seeded scratchpad must not inherit the seed's frozen footer -----

def test_agent_state_scratchpad_footer_refreshed_to_bootstrap_date(tmp_path):
    write_stale_seed(tmp_path)

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project') is True

    created = (tmp_path / '.agent-state.md').read_text(encoding='utf-8')
    assert f"*Last Updated: {TODAY}* | *Last Reviewed: {TODAY}*" in created
    assert '2020-01-01' not in created

def test_seeded_scratchpad_satisfies_documentation_review_policy(tmp_path):
    seed_path = write_stale_seed(tmp_path)

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project') is True

    # Remove the seed so only the freshly created scratchpad is under review.
    seed_path.unlink()
    assert check_docs(180, 180, 180, root_dir=tmp_path) is True

def test_agent_state_scratchpad_without_footer_is_left_for_append_timestamps(tmp_path):
    seed_path = tmp_path / AGENT_STATE_SEED_RELPATH
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text("# Scratchpad\n\nNo footer at all.\n", encoding='utf-8')

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project') is True

    created = (tmp_path / '.agent-state.md').read_text(encoding='utf-8')
    assert 'Last Updated' not in created

# --- #56: a substitution that matches nothing must abort, not warn ------------

def test_configure_language_profile_aborts_when_test_command_line_missing(tmp_path):
    agents_path = tmp_path / 'AGENTS.md'
    agents_path.write_text("# Rules\n\nNothing resembling the target line.\n", encoding='utf-8')

    with pytest.raises(SystemExit) as raised:
        configure_language_profile(tmp_path, 'python')

    assert raised.value.code == 1

# --- #55: the shipped dev requirements must be language agnostic --------------

def test_requirements_dev_excludes_python_project_test_dependencies():
    agnostic = (REPO_ROOT / 'requirements-dev.txt').read_text(encoding='utf-8')
    assert 'pytest' not in agnostic
    assert 'pre-commit' in agnostic

def test_python_project_requirements_file_carries_pytest():
    python_requirements = REPO_ROOT / 'requirements-python.txt'
    assert python_requirements.exists()
    assert 'pytest' in python_requirements.read_text(encoding='utf-8')

# --- #55: --clean-template must scrub the template's Python scaffolding -------

def make_scaffolded_tree(tmp_path: Path) -> Path:
    (tmp_path / TEMPLATE_SELF_TEST_RELPATH).mkdir(parents=True)
    (tmp_path / TEMPLATE_SELF_TEST_RELPATH / 'test_template_scripts.py').write_text(
        "# template self-test\n", encoding='utf-8')
    (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).parent.mkdir(parents=True)
    (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).write_text('"""placeholder"""\n', encoding='utf-8')
    (tmp_path / PYTHON_REQUIREMENTS_RELPATH).write_text("pytest==9.1.1\n", encoding='utf-8')
    return tmp_path

@pytest.mark.parametrize('language', ['go', 'rust', 'node', 'generic'])
def test_clean_template_scrubs_python_scaffolding_for_other_languages(tmp_path, language):
    make_scaffolded_tree(tmp_path)

    removed = clean_python_scaffolding(tmp_path, language)

    assert removed == sorted([
        PYTHON_REQUIREMENTS_RELPATH.as_posix(),
        PYTHON_PACKAGE_MARKER_RELPATH.as_posix(),
        TEMPLATE_SELF_TEST_RELPATH.as_posix(),
    ])
    assert not (tmp_path / TEMPLATE_SELF_TEST_RELPATH).exists()
    assert not (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).exists()
    assert not (tmp_path / PYTHON_REQUIREMENTS_RELPATH).exists()

def test_clean_template_keeps_python_artifacts_for_python_projects(tmp_path):
    make_scaffolded_tree(tmp_path)

    removed = clean_python_scaffolding(tmp_path, 'python')

    # The self-tests test the bootstrapper that has just run, so they go regardless.
    assert removed == [TEMPLATE_SELF_TEST_RELPATH.as_posix()]
    assert (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).exists()
    assert (tmp_path / PYTHON_REQUIREMENTS_RELPATH).exists()

def test_clean_python_scaffolding_is_idempotent(tmp_path):
    make_scaffolded_tree(tmp_path)
    clean_python_scaffolding(tmp_path, 'go')

    assert clean_python_scaffolding(tmp_path, 'go') == []

# --- #56: --dry-run must preview without mutating -----------------------------

def test_dry_run_leaves_the_language_profile_untouched(tmp_path):
    agents_path = tmp_path / 'AGENTS.md'
    original = "# Rules\n\nPrimary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`\n"
    agents_path.write_text(original, encoding='utf-8')

    configure_language_profile(tmp_path, 'rust', dry_run=True)

    assert agents_path.read_text(encoding='utf-8') == original

def test_dry_run_leaves_the_scratchpad_uncreated(tmp_path):
    write_stale_seed(tmp_path)

    assert ensure_agent_state_scratchpad(tmp_path, 'my-new-project', dry_run=True) is True
    assert not (tmp_path / '.agent-state.md').exists()

def test_dry_run_removes_no_scaffolding(tmp_path):
    make_scaffolded_tree(tmp_path)

    removed = clean_python_scaffolding(tmp_path, 'go', dry_run=True)

    assert removed == sorted([
        PYTHON_REQUIREMENTS_RELPATH.as_posix(),
        PYTHON_PACKAGE_MARKER_RELPATH.as_posix(),
        TEMPLATE_SELF_TEST_RELPATH.as_posix(),
    ])
    assert (tmp_path / TEMPLATE_SELF_TEST_RELPATH).exists()
    assert (tmp_path / PYTHON_PACKAGE_MARKER_RELPATH).exists()

# --- #56: the adopter's doctor hook is hardened to strict mode ----------------

def test_doctor_precommit_hook_is_switched_to_adopter_mode(tmp_path):
    config_path = tmp_path / PRE_COMMIT_CONFIG_RELPATH
    config_path.write_text(f"      entry: python3 {DOCTOR_TEMPLATE_MODE_ENTRY}\n", encoding='utf-8')

    assert configure_doctor_precommit_hook(tmp_path) is True

    rewritten = config_path.read_text(encoding='utf-8')
    assert DOCTOR_TEMPLATE_MODE_ENTRY not in rewritten
    assert DOCTOR_ADOPTER_MODE_ENTRY in rewritten

def test_doctor_precommit_hook_rewrite_is_skipped_in_dry_run(tmp_path):
    config_path = tmp_path / PRE_COMMIT_CONFIG_RELPATH
    original = f"      entry: python3 {DOCTOR_TEMPLATE_MODE_ENTRY}\n"
    config_path.write_text(original, encoding='utf-8')

    assert configure_doctor_precommit_hook(tmp_path, dry_run=True) is True
    assert config_path.read_text(encoding='utf-8') == original

def test_repository_seo_is_pinned_to_the_project_directory(tmp_path, monkeypatch):
    """`gh repo edit` resolves its target from the cwd, so it must run inside root_dir."""
    recorded = {}

    class SucceedingRun:
        returncode = 0
        stderr = ''

    def record_run(cmd, **kwargs):
        recorded['cwd'] = kwargs.get('cwd')
        return SucceedingRun()

    monkeypatch.setattr(bootstrap_template.shutil, 'which', lambda name: '/usr/bin/gh')
    monkeypatch.setattr(bootstrap_template.subprocess, 'run', record_run)

    configure_repository_seo(repo_topics=['ai-agent'], root_dir=tmp_path)

    assert recorded['cwd'] == tmp_path

def test_repository_seo_makes_no_remote_call_in_dry_run(tmp_path, monkeypatch):
    def forbidden_run(cmd, **kwargs):
        raise AssertionError(f"dry run must not invoke: {cmd}")

    monkeypatch.setattr(bootstrap_template.shutil, 'which', lambda name: '/usr/bin/gh')
    monkeypatch.setattr(bootstrap_template.subprocess, 'run', forbidden_run)

    configure_repository_seo(repo_topics=['ai-agent'], root_dir=tmp_path, dry_run=True)

def test_doctor_precommit_hook_absence_is_reported_not_fatal(tmp_path):
    config_path = tmp_path / PRE_COMMIT_CONFIG_RELPATH
    config_path.write_text("repos: []\n", encoding='utf-8')

    assert configure_doctor_precommit_hook(tmp_path) is False
