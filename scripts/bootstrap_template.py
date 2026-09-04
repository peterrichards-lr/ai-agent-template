#!/usr/bin/env python3
"""
bootstrap_template.py - AI Agent Quickstart Project Initializer

Configures the template repository for a new project, setting project name,
language ecosystem profiles, initial .agent-state.md scratchpad, and documentation footers.
Mutates AGENTS.md with ecosystem test commands, checks system dependencies,
installs Git hooks, and executes pre-commit quality checks.
Fails loudly if any required subprocess execution fails.
"""

import sys
import os
import json
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

SUPPORTED_LANGUAGES = ['generic', 'go', 'python', 'rust', 'java', 'node', 'cpp', 'liferay']

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

def configure_language_profile(root_dir: Path, language: str):
    """Update AGENTS.md and ecosystem settings for the selected language stack."""
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
    if agents_path.exists():
        content = agents_path.read_text(encoding='utf-8')
        target_line = f"Primary Unit Testing Command: {test_cmd}"

        import re
        content, n = re.subn(r'Primary Unit Testing Command:\s*`?[^`\n]+`?', target_line, content)
        if n > 0:
            agents_path.write_text(content, encoding='utf-8')
            print(f"  ✓ Mutated AGENTS.md with primary test command: {test_cmd}")
        else:
            print(f"  ⚠️ Warning: Could not locate Primary Unit Testing Command placeholder in AGENTS.md", file=sys.stderr)

def clean_template_meta_docs(root_dir: Path, project_name: str, language: str):
    """Remove template-only meta docs and generate a clean project README."""
    print("🧹 Cleaning template-specific meta documentation...")

    template_guide = root_dir / 'docs' / 'TEMPLATE_GUIDE.md'
    if template_guide.exists():
        template_guide.unlink()
        print("  ✓ Removed template meta-doc (docs/TEMPLATE_GUIDE.md)")

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
    readme_path.write_text(clean_readme_content, encoding='utf-8')
    print(f"  ✓ Generated clean project README.md for '{project_name}'")

def get_default_topics(language: str) -> list:
    """Return default GitHub SEO topics based on language stack."""
    base_topics = ['ai-agent', 'developer-tools']
    if language and language != 'generic':
        base_topics.append(language.lower())
    else:
        base_topics.append('template-repository')
    return base_topics

def configure_repository_seo(repo_desc: str = None, repo_topics: list = None, language: str = 'generic'):
    """Configure GitHub repository description and SEO topics via gh CLI if available."""
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

    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  ✓ Updated GitHub repository topics ({topics_csv})")
        if repo_desc:
            print(f"  ✓ Updated GitHub repository description")
    else:
        print(f"  ⚠️ Warning: Could not update GitHub repo via gh CLI (Code {res.returncode}): {res.stderr.strip()}")

def ensure_claude_skills_symlink(root_dir: Path) -> bool:
    """Ensure .claude/skills relative symlink exists and points to ../.agents/skills."""
    claude_dir = root_dir / '.claude'
    claude_skills = claude_dir / 'skills'
    target_rel = '../.agents/skills'

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

def configure_claude_settings(root_dir: Path, language: str) -> bool:
    """Configure client-side .claude/settings.json permissions per language stack."""
    claude_dir = root_dir / '.claude'
    settings_file = claude_dir / 'settings.json'

    claude_dir.mkdir(exist_ok=True)
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"  ⚠️ Warning: Could not parse {settings_file}: {e}", file=sys.stderr)
            data = {}
    else:
        data = {}

    permissions = data.setdefault("permissions", {})
    deny_list = permissions.setdefault("deny", [])

    if language == 'go':
        go_deny = "Bash(go test*)"
        if go_deny not in deny_list:
            deny_list.append(go_deny)
            print("  ✓ Configured .claude/settings.json with Go EDR test command deny-list")

    try:
        settings_file.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        return True
    except Exception as e:
        print(f"  ⚠️ Warning: Could not write {settings_file}: {e}", file=sys.stderr)
        return False

def bootstrap(
    project_name: str,
    language: str,
    non_interactive: bool = False,
    install_deps: bool = False,
    clean_template: bool = False,
    repo_desc: str = None,
    repo_topics: str = None,
    setup_branch_protection: bool = False
):
    root_dir = Path(__file__).parent.parent.resolve()
    print(f"🚀 Initializing AI Agent Project Template in: {root_dir}")
    print(f"   Project Name  : {project_name}")
    print(f"   Language Stack : {language}")
    print(f"   Non-Interactive Mode: {non_interactive}")
    print("-" * 50)

    check_system_dependencies(strict=install_deps)
    print("-" * 50)

    # 1. Optionally install dev dependencies if requested
    if install_deps:
        req_file = root_dir / 'requirements-dev.txt'
        if req_file.exists():
            print("📦 Installing development dependencies from requirements-dev.txt...")
            res = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req_file)], check=False)
            if res.returncode != 0:
                print("❌ Error: Failed to install python dependencies.", file=sys.stderr)
                sys.exit(1)

    # 2. Configure Language Profile & Clean Template Meta Docs
    configure_language_profile(root_dir, language)
    if clean_template or non_interactive:
        clean_template_meta_docs(root_dir, project_name, language)

    # 3. Update .agent-state.md and AGENTS.md
    agent_state_path = root_dir / '.agent-state.md'
    if agent_state_path.exists():
        content = agent_state_path.read_text(encoding='utf-8')
        content = content.replace('ai-agent-template', project_name)
        agent_state_path.write_text(content, encoding='utf-8')
        print(f"  ✓ Customized .agent-state.md with project name ({project_name})")

    agents_path = root_dir / 'AGENTS.md'
    if agents_path.exists():
        content = agents_path.read_text(encoding='utf-8')
        content = content.replace('ai-agent-template', project_name)
        agents_path.write_text(content, encoding='utf-8')
        print(f"  ✓ Customized AGENTS.md with project name ({project_name})")

    # 4. Ensure .claude/skills auto-discovery symlink and client settings
    ensure_claude_skills_symlink(root_dir)
    configure_claude_settings(root_dir, language)

    # 5. Append/Update timestamps
    try:
        from append_timestamps import append_timestamps
        append_timestamps(root_dir)
        print("  ✓ Processed documentation timestamp footers")
    except Exception as e:
        print(f"❌ Error running append_timestamps: {e}", file=sys.stderr)
        sys.exit(1)

    # 6. Configure GitHub Repository SEO (Description & Topics)
    parsed_topics = [t.strip() for t in repo_topics.split(',')] if repo_topics else None
    configure_repository_seo(repo_desc=repo_desc, repo_topics=parsed_topics, language=language)

    # 7. Optionally configure GitHub Branch Protection Ruleset
    if setup_branch_protection:
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
    pre_commit_config = root_dir / '.pre-commit-config.yaml'
    if pre_commit_config.exists() and shutil.which('pre-commit'):
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

    print("\n✅ Bootstrap completed successfully!")
    print(f"   Next step: Edit .agent-state.md to set your initial milestones, then begin coding!")

def main():
    parser = argparse.ArgumentParser(description="Bootstrap an AI Agent-assisted project.")
    parser.add_argument('--name', type=str, default='my-ai-project', help='Project name')
    parser.add_argument('--lang', type=str, default='generic', choices=SUPPORTED_LANGUAGES, help='Target language stack')
    parser.add_argument('-y', '--non-interactive', action='store_true', help='Run in non-interactive mode')
    parser.add_argument('--install-deps', action='store_true', help='Automatically pip install requirements-dev.txt')
    parser.add_argument('--clean-template', action='store_true', help='Clean up template meta docs and generate clean project README')
    parser.add_argument('--repo-desc', type=str, default=None, help='GitHub repository description for SEO')
    parser.add_argument('--repo-topics', type=str, default=None, help='Comma-separated list of GitHub topics for SEO')
    parser.add_argument('--setup-branch-protection', action='store_true', help='Apply GitHub branch protection ruleset via gh CLI')

    args = parser.parse_args()
    bootstrap(
        project_name=args.name,
        language=args.lang,
        non_interactive=args.non_interactive,
        install_deps=args.install_deps,
        clean_template=args.clean_template,
        repo_desc=args.repo_desc,
        repo_topics=args.repo_topics,
        setup_branch_protection=args.setup_branch_protection
    )

if __name__ == '__main__':
    main()
