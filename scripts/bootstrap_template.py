#!/usr/bin/env python3
"""
bootstrap_template.py - AI Agent Quickstart Project Initializer

Configures the template repository for a new project, setting project name,
language ecosystem profiles, initial .agent-state.md scratchpad, and documentation footers.
Mutates AGENTS.md with ecosystem test commands, checks system dependencies,
installs Git hooks, and executes pre-commit quality checks.
Fails loudly if any required subprocess execution fails, if a regex substitution
matches nothing, or if scripts/doctor.py finds a surviving placeholder at the end.
Pass --dry-run to print every planned mutation without applying any of them.
"""

import sys
import os
import re
import json
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Allow importing sibling script helpers regardless of invocation working directory
sys.path.insert(0, str(Path(__file__).parent.resolve()))
from check_docs_review import FOOTER_REGEX
from doctor import ADOPTER_MODE, run_doctor_and_report

SUPPORTED_LANGUAGES = ['generic', 'go', 'python', 'rust', 'java', 'node', 'cpp', 'liferay']

# Semgrep registry rulesets for the optional SAST layer in
# .github/workflows/security-scan.yml. The baseline is language agnostic and ships
# with the template; configure_semgrep_rulesets() appends the pack for the selected
# stack. Browse packs at https://semgrep.dev/explore
SEMGREP_BASELINE_RULESETS = ['p/ci', 'p/secrets']
SEMGREP_LANGUAGE_RULESETS = {
    'generic': [],
    'go': ['p/golang'],
    'python': ['p/python'],
    'rust': ['p/rust'],
    'java': ['p/java'],
    'node': ['p/javascript', 'p/typescript'],
    'cpp': ['p/c'],
    'liferay': ['p/java', 'p/javascript'],
}
SECURITY_SCAN_WORKFLOW_RELPATH = Path('.github') / 'workflows' / 'security-scan.yml'

# The optional MkDocs Material documentation site (see #58). It ships dormant:
# .github/workflows/docs.yml carries no automatic trigger until --docs-site
# uncomments the push block between DOCS_SITE_OPT_IN_MARKER lines, and without
# --docs-site the whole scaffold is deleted by --clean-template. Everything a
# project without a published site would otherwise carry for nothing -- a Pages
# workflow, mkdocs-material in a requirements file -- lives in these three paths.
DOCS_SITE_WORKFLOW_RELPATH = Path('.github') / 'workflows' / 'docs.yml'
DOCS_SITE_CONFIG_RELPATH = Path('mkdocs.yml')
DOCS_SITE_REQUIREMENTS_RELPATH = Path('requirements-docs.txt')
DOCS_SITE_SCAFFOLD_RELPATHS = (
    DOCS_SITE_WORKFLOW_RELPATH,
    DOCS_SITE_CONFIG_RELPATH,
    DOCS_SITE_REQUIREMENTS_RELPATH,
)
DOCS_SITE_OPT_IN_MARKER = 'OPT-IN PUSH TRIGGER'

# Community health and editor baseline files shipped as adopter-customisable stubs.
# .editorconfig carries no placeholders but is listed here so this stays the single
# canonical inventory of these files for tests and downstream tooling.
COMMUNITY_HEALTH_FILES = [
    'CODE_OF_CONDUCT.md',
    'CHANGELOG.md',
    '.editorconfig',
    '.github/CODEOWNERS',
    '.github/ISSUE_TEMPLATE/config.yml',
]

# Placeholders substituted at bootstrap time, mirroring how README/SEO metadata are seeded.
OWNER_PLACEHOLDER = '<GITHUB_OWNER_PLACEHOLDER>'
CONDUCT_EMAIL_PLACEHOLDER = '<CONDUCT_EMAIL_PLACEHOLDER>'
# Tracked seed for the gitignored .agent-state.md scratchpad, and the placeholder
# project name substituted out of it (and out of AGENTS.md) during bootstrap.
AGENT_STATE_SEED_RELPATH = Path('.agents') / 'templates' / 'agent-state.md'
TEMPLATE_PROJECT_NAME = 'ai-agent-template'

# Python-only scaffolding the template ships for its own benefit. --clean-template
# removes the self-test suite unconditionally (it tests the bootstrapper that has
# just finished running) and the Python source/dependency scaffolding for every
# language except Python. See #55.
TEMPLATE_SELF_TEST_RELPATH = Path('tests')
PYTHON_PACKAGE_MARKER_RELPATH = Path('src') / '__init__.py'
PYTHON_REQUIREMENTS_RELPATH = Path('requirements-python.txt')

# The pre-commit hook that runs the placeholder verification. The template checks
# itself in template mode; the adopter's repository is checked strictly.
PRE_COMMIT_CONFIG_RELPATH = Path('.pre-commit-config.yaml')
DOCTOR_TEMPLATE_MODE_ENTRY = 'scripts/doctor.py --mode template'
DOCTOR_ADOPTER_MODE_ENTRY = 'scripts/doctor.py'

def announce_planned_write(rel_path, summary: str):
    """Print the mutation a dry run would have made instead of making it."""
    print(f"  [dry-run] would update {rel_path}: {summary}")

def check_system_dependencies(strict: bool = False):
    """Verify presence of essential tools: python >= 3.8, git, gh, pre-commit."""
    print("🔍 Checking system dependencies...")

    py_version = sys.version_info
    if py_version < (3, 8):
        print(f"❌ Error: Python 3.8+ is required. Found Python {py_version.major}.{py_version.minor}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ Python {py_version.major}.{py_version.minor}.{py_version.micro}")

    git_bin = shutil.which('git')
    if not git_bin:
        print("❌ Error: Git is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ Git found: {git_bin}")

    gh_bin = shutil.which('gh')
    if gh_bin:
        print(f"  ✓ GitHub CLI (gh) found: {gh_bin}")
    else:
        print("  ⚠️ Warning: GitHub CLI (gh) not found. Issue sync features require gh CLI.")

    precommit_bin = shutil.which('pre-commit')
    if precommit_bin:
        print(f"  ✓ pre-commit found: {precommit_bin}")
    else:
        print("  ⚠️ Warning: pre-commit tool not found in PATH.")
        print("     To install: pip install -r requirements-dev.txt")
        if strict:
            print("❌ Error: pre-commit is required in strict mode.", file=sys.stderr)
            sys.exit(1)

def configure_language_profile(root_dir: Path, language: str, dry_run: bool = False):
    """Update AGENTS.md and ecosystem settings for the selected language stack.

    Aborts when the target line cannot be located: leaving <TEST_COMMAND_PLACEHOLDER>
    live in AGENTS.md hands every agent a placeholder where the command that gates
    "work complete" should be, and a warning on stderr is not loud enough for that.
    """
    print(f"🛠️ Configuring language profile for: {language}...")

    if language == 'go':
        # Never bare `go test`/`go test ./...` -- it compiles an unsigned
        # test binary into the OS default temp dir and executes it, which
        # trips behavior-based endpoint security (SentinelOne, CrowdStrike,
        # etc.) for any package under test that opens a real network
        # listener (httptest.Server, a WebSocket server, ...). Build named
        # test binaries explicitly into a directory the project controls
        # instead. See docs/TEMPLATE_GUIDE.md's EDR-safe testing note.
        test_cmd = ('`go test -c -o <test-dir>/<pkg>.test <import-path>` per package '
                    '(loop over `go list -f \'{{if .TestGoFiles}}{{.ImportPath}}{{end}}\' ./...`), '
                    'then run each binary directly -- never bare `go test`/`go test ./...`')
    elif language == 'python':
        test_cmd = '`pytest -v --tb=short`'
    elif language == 'rust':
        test_cmd = '`cargo test --quiet`'
    elif language == 'java':
        test_cmd = '`mvn test -B`'
    elif language == 'node':
        test_cmd = '`npm test -- --ci`'
    elif language == 'cpp':
        test_cmd = '`ctest --output-on-failure`'
    elif language == 'liferay':
        test_cmd = '`./gradlew test`'
    else:
        test_cmd = '`the ecosystem non-interactive test command`'

    # Mutate AGENTS.md with test_cmd
    agents_path = root_dir / 'AGENTS.md'
    if not agents_path.exists():
        print("❌ Error: AGENTS.md not found; cannot set the primary unit testing command.", file=sys.stderr)
        sys.exit(1)

    content = agents_path.read_text(encoding='utf-8')
    target_line = f"Primary Unit Testing Command: {test_cmd}"

    content, n = re.subn(r'Primary Unit Testing Command:\s*`?[^`\n]+`?', target_line, content)
    if n == 0:
        print(
            "❌ Error: Could not locate the 'Primary Unit Testing Command:' line in AGENTS.md.\n"
            "   Bootstrap cannot leave <TEST_COMMAND_PLACEHOLDER> live: unit-testing/SKILL.md makes\n"
            "   running that command the gate on declaring work complete. Restore the line from the\n"
            "   template's AGENTS.md, then re-run bootstrap.",
            file=sys.stderr
        )
        sys.exit(1)

    if dry_run:
        announce_planned_write('AGENTS.md', f"primary test command -> {test_cmd}")
        return

    agents_path.write_text(content, encoding='utf-8')
    print(f"  ✓ Mutated AGENTS.md with primary test command: {test_cmd}")

def configure_semgrep_rulesets(root_dir: Path, language: str, dry_run: bool = False) -> bool:
    """Select the Semgrep registry rulesets for the chosen stack in security-scan.yml.

    Rewrites the single SEMGREP_RULESETS env line so the optional SAST workflow scans
    with the language pack that matches the project instead of the generic baseline.
    Returns False (without failing the bootstrap) when the optional security layer has
    been deleted or the knob cannot be found, since neither is fatal to a new project.
    """
    workflow_path = root_dir / SECURITY_SCAN_WORKFLOW_RELPATH

    if not workflow_path.exists():
        print(f"  ⚠️ Skipping Semgrep ruleset selection: {SECURITY_SCAN_WORKFLOW_RELPATH} not found.")
        return False

    rulesets = SEMGREP_BASELINE_RULESETS + SEMGREP_LANGUAGE_RULESETS.get(language, [])
    replacement = f'SEMGREP_RULESETS: "{" ".join(rulesets)}"'

    content = workflow_path.read_text(encoding='utf-8')
    content, n = re.subn(r'SEMGREP_RULESETS:\s*"[^"]*"', replacement, content)
    if n == 0:
        print(f"  ⚠️ Warning: Could not locate the SEMGREP_RULESETS knob in {SECURITY_SCAN_WORKFLOW_RELPATH}.", file=sys.stderr)
        return False

    if dry_run:
        announce_planned_write(SECURITY_SCAN_WORKFLOW_RELPATH.as_posix(), replacement)
        return True

    workflow_path.write_text(content, encoding='utf-8')
    print(f"  ✓ Selected Semgrep rulesets for {language}: {' '.join(rulesets)}")
    return True

def uncomment_marked_block(content: str, marker: str) -> tuple:
    """Uncomment the lines between the two `marker` lines, dropping the markers.

    The template ships opt-in YAML commented out rather than absent so a reader can
    see exactly what enabling it does, and so `actionlint` and `check-yaml` still
    parse the file. Returns (content, number of lines uncommented); a zero count
    means the marked block was not found.
    """
    lines = content.splitlines(keepends=True)
    bounds = [index for index, line in enumerate(lines) if marker in line]
    if len(bounds) != 2:
        return content, 0

    start, end = bounds
    body = [re.sub(r'^(\s*)#[ ]?', r'\1', line) for line in lines[start + 1:end]]
    return ''.join(lines[:start] + body + lines[end + 1:]), len(body)


def enable_docs_site(root_dir: Path, project_name: str, repo_owner: str = None,
                     dry_run: bool = False) -> bool:
    """Activate the opt-in MkDocs site: seed mkdocs.yml and arm the Pages workflow.

    Aborts when a shipped file is present but its knob has gone missing. The adopter
    asked for a documentation site by name; silently handing them a workflow that
    never fires would be a worse outcome than a failed bootstrap.
    """
    print("📚 Enabling the optional documentation site...")

    workflow_path = root_dir / DOCS_SITE_WORKFLOW_RELPATH
    config_path = root_dir / DOCS_SITE_CONFIG_RELPATH

    missing = [rel.as_posix() for rel in (DOCS_SITE_WORKFLOW_RELPATH, DOCS_SITE_CONFIG_RELPATH)
               if not (root_dir / rel).exists()]
    if missing:
        print(f"  ⚠️ Skipping --docs-site: {', '.join(missing)} not found.", file=sys.stderr)
        return False

    workflow, uncommented = uncomment_marked_block(
        workflow_path.read_text(encoding='utf-8'), DOCS_SITE_OPT_IN_MARKER)
    if uncommented == 0:
        print(f"❌ Error: Could not find the '{DOCS_SITE_OPT_IN_MARKER}' block in "
              f"{DOCS_SITE_WORKFLOW_RELPATH.as_posix()}; the site would never deploy.",
              file=sys.stderr)
        sys.exit(1)

    config = config_path.read_text(encoding='utf-8')
    config, named = re.subn(r'^site_name:.*$', lambda _: f'site_name: {project_name}',
                            config, count=1, flags=re.MULTILINE)
    if named == 0:
        print(f"❌ Error: Could not find the site_name knob in "
              f"{DOCS_SITE_CONFIG_RELPATH.as_posix()}.", file=sys.stderr)
        sys.exit(1)

    # site_url/repo_url ship commented out: a canonical URL pointing at the template's
    # own Pages site is worse than no canonical URL at all. Seed them only when the
    # owner is known.
    if repo_owner:
        pages_url = f'https://{repo_owner}.github.io/{project_name}/'
        repo_url = f'https://github.com/{repo_owner}/{project_name}'
        config, _ = re.subn(r'^#\s*site_url:.*$', lambda _: f'site_url: {pages_url}',
                            config, count=1, flags=re.MULTILINE)
        config, _ = re.subn(r'^#\s*repo_url:.*$', lambda _: f'repo_url: {repo_url}',
                            config, count=1, flags=re.MULTILINE)

    if dry_run:
        announce_planned_write(DOCS_SITE_WORKFLOW_RELPATH.as_posix(),
                               "activate the GitHub Pages push trigger")
        announce_planned_write(DOCS_SITE_CONFIG_RELPATH.as_posix(),
                               f"seed site_name/site_url/repo_url for '{project_name}'")
        return True

    workflow_path.write_text(workflow, encoding='utf-8')
    config_path.write_text(config, encoding='utf-8')
    print(f"  ✓ Armed the GitHub Pages push trigger in {DOCS_SITE_WORKFLOW_RELPATH.as_posix()}")
    print(f"  ✓ Seeded {DOCS_SITE_CONFIG_RELPATH.as_posix()} for '{project_name}'")
    print("  ℹ️ Set Settings > Pages > Source to 'GitHub Actions' before the first deploy.")
    return True


def clean_docs_site_scaffold(root_dir: Path, docs_site: bool, dry_run: bool = False) -> list:
    """Remove the optional documentation site unless the adopter opted into it.

    The Diátaxis directories under docs/ are deliberately NOT removed: organising
    documentation into tutorials/how-to/reference/explanation is worth doing whether
    or not the result is ever rendered into a site.

    Returns the sorted relative POSIX paths that were (or, in a dry run, would be) removed.
    """
    if docs_site:
        return []

    removed = []
    for rel_path in DOCS_SITE_SCAFFOLD_RELPATHS:
        target = root_dir / rel_path
        if not target.exists():
            continue

        removed.append(rel_path.as_posix())
        if dry_run:
            announce_planned_write(rel_path.as_posix(), "remove the opt-in documentation site")
            continue

        target.unlink()
        print(f"  ✓ Removed the opt-in documentation site ({rel_path.as_posix()})")

    return sorted(removed)


def clean_python_scaffolding(root_dir: Path, language: str, dry_run: bool = False) -> list:
    """Remove the Python-only scaffolding the template ships for its own benefit.

    The self-test suite tests the bootstrapper that has just finished running, so it is
    dead weight in every adopter's repository. src/__init__.py and requirements-python.txt
    are Python artefacts and are kept only for --lang python. See #55.

    Returns the sorted relative POSIX paths that were (or, in a dry run, would be) removed.
    """
    removable = [TEMPLATE_SELF_TEST_RELPATH]
    if language != 'python':
        removable.extend([PYTHON_PACKAGE_MARKER_RELPATH, PYTHON_REQUIREMENTS_RELPATH])

    removed = []
    for rel_path in removable:
        target = root_dir / rel_path
        if not target.exists():
            continue

        removed.append(rel_path.as_posix())
        if dry_run:
            announce_planned_write(rel_path.as_posix(), "remove template Python scaffolding")
            continue

        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        print(f"  ✓ Removed template Python scaffolding ({rel_path.as_posix()})")

    return sorted(removed)

def clean_template_meta_docs(root_dir: Path, project_name: str, language: str,
                             dry_run: bool = False, docs_site: bool = False):
    """Remove template-only meta docs and generate a clean project README."""
    print("🧹 Cleaning template-specific meta documentation...")

    template_guide = root_dir / 'docs' / 'TEMPLATE_GUIDE.md'
    if template_guide.exists():
        if dry_run:
            announce_planned_write('docs/TEMPLATE_GUIDE.md', "remove template meta-doc")
        else:
            template_guide.unlink()
            print("  ✓ Removed template meta-doc (docs/TEMPLATE_GUIDE.md)")

    clean_python_scaffolding(root_dir, language, dry_run=dry_run)
    clean_docs_site_scaffold(root_dir, docs_site, dry_run=dry_run)

    today_str = datetime.today().strftime('%Y-%m-%d')
    clean_readme_content = f"""# {project_name}

Core application built with **{language.capitalize()}** using AI Agent-Assisted Development.

---

## Overview

[Provide a high-level summary of {project_name}, its architecture, and business value.]

---

## Getting Started

### Prerequisites
- Language runtime for **{language.capitalize()}**
- Python 3.8+ (for pre-commit hooks and documentation helpers)
- Git & GitHub CLI (`gh`)

### Quick Setup

```bash
# Install development quality gate dependencies
pip install -r requirements-dev.txt

# Install Git pre-commit hooks
pre-commit install

# Run pre-commit quality checks locally
pre-commit run --all-files
```

---

## AI Agent Pair Programming Workflow

This repository uses **Agent Skills** located in `.agents/skills/` and persistent state tracking in `.agent-state.md`:

- **Master Routing Index**: Refer to [`AGENTS.md`](AGENTS.md) for available agent skills and rules of engagement.
- **Provider Discovery**: Discovery files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`) redirect to `AGENTS.md`.
- **Session State**: Update [`.agent-state.md`](.agent-state.md) before starting major milestones or architectural changes.
- **Documentation Verification**: Run `python3 scripts/append_timestamps.py` and `python3 scripts/check_docs_review.py` after implementing features.

---

## License

This project is licensed under the [MIT License](LICENSE).

<!-- markdownlint-disable MD049 -->
---
*Last Updated: {today_str}* | *Last Reviewed: {today_str}*
"""
    readme_path = root_dir / 'README.md'
    if dry_run:
        announce_planned_write('README.md', f"replace with a clean project README for '{project_name}'")
        return

    readme_path.write_text(clean_readme_content, encoding='utf-8')
    print(f"  ✓ Generated clean project README.md for '{project_name}'")

def substitute_community_health_placeholders(
    root_dir: Path,
    project_name: str,
    repo_owner: str = None,
    conduct_email: str = None,
    dry_run: bool = False
) -> list:
    """Seed community health stubs with the project name, GitHub owner and conduct contact.

    Mirrors how the project name is seeded into AGENTS.md/.agent-state.md. --repo-owner and
    --conduct-email are required on the command line, so a placeholder surviving here means a
    direct caller omitted a value; it is left in place and reported, and bootstrap's final
    doctor run then fails on it rather than shipping it.

    Returns the sorted relative paths of files still containing an unresolved placeholder.
    """
    print("🤝 Seeding community health files...")

    replacements = [(TEMPLATE_PROJECT_NAME, project_name)]
    if repo_owner:
        replacements.append((OWNER_PLACEHOLDER, repo_owner))
    if conduct_email:
        replacements.append((CONDUCT_EMAIL_PLACEHOLDER, conduct_email))

    unresolved = []
    for rel_path in COMMUNITY_HEALTH_FILES:
        target = root_dir / rel_path
        if not target.exists():
            continue

        original = target.read_text(encoding='utf-8')
        content = original
        for placeholder, value in replacements:
            content = content.replace(placeholder, value)

        if content != original:
            if dry_run:
                announce_planned_write(rel_path, "substitute community health placeholders")
            else:
                target.write_text(content, encoding='utf-8')
                print(f"  ✓ Customized {rel_path}")

        if OWNER_PLACEHOLDER in content or CONDUCT_EMAIL_PLACEHOLDER in content:
            unresolved.append(rel_path)

    if unresolved:
        print(
            "  ⚠️ Warning: unresolved placeholders remain in: " + ", ".join(sorted(unresolved)) + "\n"
            "     Re-run with --repo-owner and/or --conduct-email, or edit the files by hand.",
            file=sys.stderr
        )

    return sorted(unresolved)

def get_default_topics(language: str) -> list:
    """Return default GitHub SEO topics based on language stack."""
    base_topics = ['ai-agent', 'developer-tools']
    if language and language != 'generic':
        base_topics.append(language.lower())
    else:
        base_topics.append('template-repository')
    return base_topics

def configure_repository_seo(repo_desc: str = None, repo_topics: list = None, language: str = 'generic',
                             root_dir: Path = None, dry_run: bool = False):
    """Configure GitHub repository description and SEO topics via gh CLI if available.

    `gh repo edit` resolves its target from the working directory's git remote, so the
    call is pinned to root_dir. Without that, bootstrapping a project from a different
    working directory silently rewrites the topics of whichever repository the shell
    happens to be sitting in -- an irreversible mutation of the wrong remote.
    """
    gh_bin = shutil.which('gh')
    if not gh_bin:
        print("  ⚠️ Skipping GitHub SEO configuration: gh CLI not found in PATH.")
        return

    topics = repo_topics if repo_topics else get_default_topics(language)
    topics_csv = ",".join([t.strip() for t in topics if t.strip()])

    print(f"🏷️ Configuring GitHub Repository SEO (Topics: {topics_csv})...")
    cmd = [gh_bin, 'repo', 'edit', '--add-topic', topics_csv]
    if repo_desc:
        cmd.extend(['--description', repo_desc])

    if dry_run:
        print(f"  [dry-run] would run (in {root_dir}): {' '.join(cmd)}")
        return

    res = subprocess.run(cmd, cwd=root_dir, check=False, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  ✓ Updated GitHub repository topics ({topics_csv})")
        if repo_desc:
            print(f"  ✓ Updated GitHub repository description")
    else:
        print(f"  ⚠️ Warning: Could not update GitHub repo via gh CLI (Code {res.returncode}): {res.stderr.strip()}")

def ensure_claude_skills_symlink(root_dir: Path, dry_run: bool = False) -> bool:
    """Ensure .claude/skills relative symlink exists and points to ../.agents/skills."""
    claude_dir = root_dir / '.claude'
    claude_skills = claude_dir / 'skills'
    target_rel = '../.agents/skills'

    if dry_run:
        if claude_skills.is_dir() and claude_skills.is_symlink():
            print("  [dry-run] .claude/skills symlink already correct; no change")
        else:
            announce_planned_write('.claude/skills', f"create symlink -> {target_rel}")
        return True

    claude_dir.mkdir(exist_ok=True)

    if claude_skills.is_symlink():
        current_target = os.readlink(claude_skills).replace('\\', '/')
        if current_target == target_rel:
            print("  ✓ Verified .claude/skills symlink -> ../.agents/skills")
            return True
        claude_skills.unlink()

    if claude_skills.exists() and not claude_skills.is_symlink():
        print(
            "  ⚠️ Warning: .claude/skills exists but is not a symlink.\n"
            "     On Windows, ensure Git has core.symlinks enabled: git config core.symlinks true\n"
            "     or enable Windows Developer Mode.",
            file=sys.stderr
        )
        return False

    try:
        os.symlink(target_rel, claude_skills, target_is_directory=True)
        print("  ✓ Created .claude/skills symlink -> ../.agents/skills")
        return True
    except OSError as e:
        print(
            f"  ⚠️ Warning: Could not create .claude/skills symlink: {e}\n"
            "     On Windows, symlinks require 'git config core.symlinks true' or Windows Developer Mode.",
            file=sys.stderr
        )
        return False

def refresh_timestamp_footer(content: str, today_str: str) -> str:
    """Rewrite an existing Last Updated / Last Reviewed footer to today's date.

    The seed's footer is frozen at the date the seed was last edited, and
    append_timestamps.py only injects missing footers -- it never refreshes one. Left
    alone, a project bootstrapped more than 180 days after the seed was bumped is born
    violating the documentation review policy, and bootstrap's own pre-commit step then
    fails on a file bootstrap wrote seconds earlier. See #80.

    Content with no footer is returned unchanged, for append_timestamps.py to inject one.
    """
    refreshed_footer = f"*Last Updated: {today_str}* | *Last Reviewed: {today_str}*"
    return FOOTER_REGEX.sub(refreshed_footer, content)

def ensure_agent_state_scratchpad(root_dir: Path, project_name: str, dry_run: bool = False) -> bool:
    """Seed .agent-state.md from the tracked template when absent, then apply the project name.

    In a fresh clone .agent-state.md does not exist (it is gitignored), so this step
    must create it rather than skip. Reports created / customized / failed explicitly.
    """
    agent_state_path = root_dir / '.agent-state.md'
    seed_path = root_dir / AGENT_STATE_SEED_RELPATH

    if not agent_state_path.exists():
        if not seed_path.exists():
            print(
                f"  ⚠️ Warning: Could not create .agent-state.md: missing seed template {AGENT_STATE_SEED_RELPATH.as_posix()}\n"
                "     Restore it from the template repository, then re-run bootstrap.",
                file=sys.stderr
            )
            return False
        if dry_run:
            announce_planned_write(
                '.agent-state.md',
                f"create from {AGENT_STATE_SEED_RELPATH.as_posix()}, set project name and refresh footer"
            )
            return True
        try:
            shutil.copyfile(seed_path, agent_state_path)
            print(f"  ✓ Created .agent-state.md from {AGENT_STATE_SEED_RELPATH.as_posix()}")
        except OSError as e:
            print(f"  ⚠️ Warning: Could not create .agent-state.md: {e}", file=sys.stderr)
            return False

    today_str = datetime.today().strftime('%Y-%m-%d')
    try:
        content = agent_state_path.read_text(encoding='utf-8')
        content = content.replace(TEMPLATE_PROJECT_NAME, project_name)
        content = refresh_timestamp_footer(content, today_str)
        if dry_run:
            announce_planned_write('.agent-state.md', f"set project name and refresh footer to {today_str}")
            return True
        agent_state_path.write_text(content, encoding='utf-8')
    except OSError as e:
        print(f"  ⚠️ Warning: Could not customize .agent-state.md: {e}", file=sys.stderr)
        return False

    print(f"  ✓ Customized .agent-state.md with project name ({project_name}) and footer date ({today_str})")
    return True

def configure_claude_settings(root_dir: Path, language: str, dry_run: bool = False) -> bool:
    """Configure client-side .claude/settings.json permissions per language stack."""
    claude_dir = root_dir / '.claude'
    settings_file = claude_dir / 'settings.json'

    if not settings_file.exists():
        print(f"  ⚠️ Warning: {settings_file} does not exist. Skipping Claude settings configuration.", file=sys.stderr)
        return False

    try:
        data = json.loads(settings_file.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"  ⚠️ Warning: Could not parse {settings_file}: {e}. Preserving existing file without modification.", file=sys.stderr)
        return False

    permissions = data.setdefault("permissions", {})
    deny_list = permissions.setdefault("deny", [])

    if language == 'go':
        go_denies = ["Bash(go test)", "Bash(go test ./...)"]
        added = []
        for gd in go_denies:
            if gd not in deny_list:
                deny_list.append(gd)
                added.append(gd)
        if added:
            print(f"  ✓ Configured .claude/settings.json with Go EDR test command deny-list ({', '.join(added)})")

    if dry_run:
        announce_planned_write('.claude/settings.json', f"apply {language} permission deny-list")
        return True

    try:
        settings_file.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        return True
    except Exception as e:
        print(f"  ⚠️ Warning: Could not write {settings_file}: {e}", file=sys.stderr)
        return False

def configure_doctor_precommit_hook(root_dir: Path, dry_run: bool = False) -> bool:
    """Switch the doctor pre-commit hook from template mode to strict adopter mode.

    The template's own config exempts the un-bootstrapped stubs it is supposed to still
    carry. Once bootstrap has substituted them, the adopter's repository must be checked
    strictly so a placeholder reintroduced later is caught. Not fatal when the hook is
    absent: .pre-commit-config.yaml is an adopter-editable file. See #56.
    """
    config_path = root_dir / PRE_COMMIT_CONFIG_RELPATH

    if not config_path.exists():
        print(f"  ⚠️ Skipping doctor hook configuration: {PRE_COMMIT_CONFIG_RELPATH.as_posix()} not found.")
        return False

    content = config_path.read_text(encoding='utf-8')

    if DOCTOR_TEMPLATE_MODE_ENTRY not in content:
        if DOCTOR_ADOPTER_MODE_ENTRY in content:
            print("  ✓ Doctor pre-commit hook already runs in strict adopter mode")
            return True
        print(
            f"  ⚠️ Warning: no doctor hook found in {PRE_COMMIT_CONFIG_RELPATH.as_posix()}; "
            "placeholders reintroduced later will not be caught on commit.",
            file=sys.stderr
        )
        return False

    if dry_run:
        announce_planned_write(
            PRE_COMMIT_CONFIG_RELPATH.as_posix(),
            f"switch doctor hook to '{DOCTOR_ADOPTER_MODE_ENTRY}' (strict adopter mode)"
        )
        return True

    config_path.write_text(
        content.replace(DOCTOR_TEMPLATE_MODE_ENTRY, DOCTOR_ADOPTER_MODE_ENTRY), encoding='utf-8')
    print("  ✓ Switched doctor pre-commit hook to strict adopter mode")
    return True

def bootstrap(
    project_name: str,
    language: str,
    non_interactive: bool = False,
    install_deps: bool = False,
    clean_template: bool = False,
    repo_desc: str = None,
    repo_topics: str = None,
    setup_branch_protection: bool = False,
    repo_owner: str = None,
    conduct_email: str = None,
    dry_run: bool = False,
    docs_site: bool = False
):
    root_dir = Path(__file__).parent.parent.resolve()
    print(f"🚀 Initializing AI Agent Project Template in: {root_dir}")
    print(f"   Project Name  : {project_name}")
    print(f"   Language Stack : {language}")
    print(f"   Non-Interactive Mode: {non_interactive}")
    if dry_run:
        print("   Dry Run: no file, repository or hook will be modified")
    print("-" * 50)

    check_system_dependencies(strict=install_deps)
    print("-" * 50)

    # 1. Optionally install dev dependencies if requested
    if install_deps:
        req_files = [root_dir / 'requirements-dev.txt']
        if language == 'python':
            req_files.append(root_dir / PYTHON_REQUIREMENTS_RELPATH)
        present = [str(req_file) for req_file in req_files if req_file.exists()]
        if present and dry_run:
            print(f"  [dry-run] would run: pip install -r {' -r '.join(present)}")
        elif present:
            print(f"📦 Installing development dependencies from {', '.join(present)}...")
            cmd = [sys.executable, '-m', 'pip', 'install']
            for req_path in present:
                cmd.extend(['-r', req_path])
            res = subprocess.run(cmd, check=False)
            if res.returncode != 0:
                print("❌ Error: Failed to install python dependencies.", file=sys.stderr)
                sys.exit(1)

    # 2. Configure Language Profile & Clean Template Meta Docs
    configure_language_profile(root_dir, language, dry_run=dry_run)
    configure_semgrep_rulesets(root_dir, language, dry_run=dry_run)
    if docs_site:
        enable_docs_site(root_dir, project_name, repo_owner=repo_owner, dry_run=dry_run)
    if clean_template or non_interactive:
        clean_template_meta_docs(root_dir, project_name, language, dry_run=dry_run,
                                 docs_site=docs_site)

    # 3. Seed/update .agent-state.md and update AGENTS.md
    ensure_agent_state_scratchpad(root_dir, project_name, dry_run=dry_run)

    agents_path = root_dir / 'AGENTS.md'
    if agents_path.exists():
        content = agents_path.read_text(encoding='utf-8')
        content = content.replace(TEMPLATE_PROJECT_NAME, project_name)
        if dry_run:
            announce_planned_write('AGENTS.md', f"substitute project name ({project_name})")
        else:
            agents_path.write_text(content, encoding='utf-8')
            print(f"  ✓ Customized AGENTS.md with project name ({project_name})")

    # 4. Ensure .claude/skills auto-discovery symlink and client settings
    ensure_claude_skills_symlink(root_dir, dry_run=dry_run)
    configure_claude_settings(root_dir, language, dry_run=dry_run)

    # 4b. Seed community health stubs (Code of Conduct, changelog, CODEOWNERS, issue chooser)
    substitute_community_health_placeholders(
        root_dir,
        project_name=project_name,
        repo_owner=repo_owner,
        conduct_email=conduct_email,
        dry_run=dry_run
    )

    # 4c. Harden the adopter's placeholder verification hook
    configure_doctor_precommit_hook(root_dir, dry_run=dry_run)

    # 5. Append/Update timestamps
    if dry_run:
        print("  [dry-run] would inject missing documentation timestamp footers")
    else:
        try:
            from append_timestamps import append_timestamps
            append_timestamps(root_dir)
            print("  ✓ Processed documentation timestamp footers")
        except Exception as e:
            print(f"❌ Error running append_timestamps: {e}", file=sys.stderr)
            sys.exit(1)

    # 6. Configure GitHub Repository SEO (Description & Topics)
    parsed_topics = [t.strip() for t in repo_topics.split(',')] if repo_topics else None
    configure_repository_seo(
        repo_desc=repo_desc, repo_topics=parsed_topics, language=language,
        root_dir=root_dir, dry_run=dry_run)

    # 7. Optionally configure GitHub Branch Protection Ruleset
    if setup_branch_protection and dry_run:
        print("  [dry-run] would apply the GitHub branch protection ruleset via gh CLI")
    elif setup_branch_protection:
        ruleset_file = root_dir / '.github' / 'rulesets' / 'protect-main-branch.json'
        if not ruleset_file.exists():
            print(f"❌ Error: Required branch protection ruleset file not found: {ruleset_file}", file=sys.stderr)
            sys.exit(1)

        try:
            from setup_branch_protection import apply_branch_protection
            if not apply_branch_protection(ruleset_file):
                print(
                    "  ⚠️ Warning: Branch protection ruleset could not be applied automatically (requires admin PAT).\n"
                    f"     Run manually: gh api --method POST 'repos/{{owner}}/{{repo}}/rulesets' --input {ruleset_file}",
                    file=sys.stderr
                )
        except Exception as e:
            print(
                f"  ⚠️ Warning: Could not apply branch protection ruleset: {e}\n"
                f"     Run manually: gh api --method POST 'repos/{{owner}}/{{repo}}/rulesets' --input {ruleset_file}",
                file=sys.stderr
            )

    # 8. Pre-commit setup readiness & local verification check
    pre_commit_config = root_dir / PRE_COMMIT_CONFIG_RELPATH
    if dry_run:
        print("  [dry-run] would install Git pre-commit hooks and run `pre-commit run --all-files`")
    elif pre_commit_config.exists() and shutil.which('pre-commit'):
        print("  ✓ Installing Git pre-commit hooks...")
        res_inst = subprocess.run(['pre-commit', 'install'], cwd=root_dir, check=False)
        if res_inst.returncode != 0:
            print("❌ Error: Failed to install pre-commit hooks.", file=sys.stderr)
            sys.exit(1)

        print("  🧪 Running local pre-commit quality gate checks...")
        res_run = subprocess.run(['pre-commit', 'run', '--all-files'], cwd=root_dir, check=False)
        if res_run.returncode != 0:
            print("❌ Error: Pre-commit quality gate checks failed.", file=sys.stderr)
            print("   Please review and resolve pre-commit errors before completing bootstrap.", file=sys.stderr)
            sys.exit(1)

    # 9. Verify the end state. Every mutation above is a regex or copy that can miss;
    #    without this the script reports success on a repository still carrying live
    #    placeholders. See #56.
    if dry_run:
        print("\n✅ Dry run complete. No files were modified; re-run without --dry-run to apply.")
        return

    print("  🩺 Verifying no template placeholders survived...")
    if not run_doctor_and_report(root_dir, mode=ADOPTER_MODE):
        print(
            "❌ Error: Bootstrap left unresolved template placeholders (listed above).\n"
            "   Supply the missing values (e.g. --repo-owner, --conduct-email) or edit the\n"
            "   cited lines by hand, then re-run bootstrap.",
            file=sys.stderr
        )
        sys.exit(1)

    print("\n✅ Bootstrap completed successfully!")
    print(f"   Next step: Edit .agent-state.md to set your initial milestones, then begin coding!")

def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. Exposed separately so tests can validate documented invocations."""
    parser = argparse.ArgumentParser(
        description="Bootstrap an AI Agent-assisted project.",
        epilog=(
            "--name, --repo-owner and --conduct-email are required: each is substituted into "
            "files the agent rules and community health docs depend on, and bootstrap's final "
            "verification (scripts/doctor.py) rejects any placeholder left unresolved. Requiring "
            "them here turns a missing value into a usage error before any file is modified."
        )
    )
    # Required rather than defaulted. A default project name would be written into a dozen
    # files and then rejected by the doctor as an unresolved placeholder -- the substitution
    # and the verification must not disagree about what a real value looks like.
    parser.add_argument('--name', type=str, required=True, help='Project name (required)')
    parser.add_argument('--lang', type=str, default='generic', choices=SUPPORTED_LANGUAGES, help='Target language stack')
    parser.add_argument('-y', '--non-interactive', action='store_true', help='Run in non-interactive mode')
    parser.add_argument('--install-deps', action='store_true', help='Automatically pip install requirements-dev.txt (plus requirements-python.txt for --lang python)')
    parser.add_argument('--dry-run', action='store_true', help='Preview every planned mutation without modifying files, repository settings or Git hooks')
    parser.add_argument('--clean-template', action='store_true', help='Clean up template meta docs and generate clean project README')
    parser.add_argument('--repo-desc', type=str, default=None, help='GitHub repository description for SEO')
    parser.add_argument('--repo-topics', type=str, default=None, help='Comma-separated list of GitHub topics for SEO')
    parser.add_argument('--setup-branch-protection', action='store_true', help='Apply GitHub branch protection ruleset via gh CLI')
    # Opt-in, never a default. A project with no documentation site is better served by
    # not carrying mkdocs.yml, a Pages workflow and mkdocs-material at all than by
    # carrying them switched off, so --clean-template deletes the scaffold without this.
    parser.add_argument('--docs-site', action='store_true', help='Enable the optional MkDocs Material documentation site and its GitHub Pages workflow (without this, --clean-template removes mkdocs.yml, .github/workflows/docs.yml and requirements-docs.txt)')
    parser.add_argument('--repo-owner', type=str, required=True, help='GitHub org/user owning the repository, seeding CODEOWNERS, CHANGELOG links and the issue chooser (required)')
    parser.add_argument('--conduct-email', type=str, required=True, help='Code of Conduct enforcement contact email address (required)')

    return parser

def main():
    args = build_arg_parser().parse_args()
    bootstrap(
        project_name=args.name,
        language=args.lang,
        non_interactive=args.non_interactive,
        install_deps=args.install_deps,
        clean_template=args.clean_template,
        repo_desc=args.repo_desc,
        repo_topics=args.repo_topics,
        setup_branch_protection=args.setup_branch_protection,
        repo_owner=args.repo_owner,
        conduct_email=args.conduct_email,
        dry_run=args.dry_run,
        docs_site=args.docs_site
    )

if __name__ == '__main__':
    main()
