#!/usr/bin/env python3
"""
bootstrap_template.py - AI Agent Quickstart Project Initializer

Configures the template repository for a new project, setting project name,
language ecosystem profiles, initial GEMINI.md state, and documentation footers.
Checks for local tool dependencies (Python 3, Git, gh CLI, pre-commit) and
ensures clean execution in both local and GitHub Actions CI environments.
"""

import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

SUPPORTED_LANGUAGES = ['generic', 'go', 'python', 'rust', 'java', 'node', 'liferay']

def check_system_dependencies():
    """Verify presence of essential tools: python >= 3.8, git, gh, pre-commit."""
    print("🔍 Checking system dependencies...")
    
    # 1. Python version check
    py_version = sys.version_info
    if py_version < (3, 8):
        print(f"❌ Error: Python 3.8+ is required. Found Python {py_version.major}.{py_version.minor}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ Python {py_version.major}.{py_version.minor}.{py_version.micro}")

    # 2. Git check
    git_bin = shutil.which('git')
    if not git_bin:
        print("❌ Error: Git is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ Git found: {git_bin}")

    # 3. GitHub CLI (gh) check
    gh_bin = shutil.which('gh')
    if gh_bin:
        print(f"  ✓ GitHub CLI (gh) found: {gh_bin}")
    else:
        print("  ⚠️ Warning: GitHub CLI (gh) not found. Some issue sync features will require gh CLI.")

    # 4. Pre-commit check
    precommit_bin = shutil.which('pre-commit')
    if precommit_bin:
        print(f"  ✓ pre-commit found: {precommit_bin}")
    else:
        print("  ⚠️ Warning: pre-commit tool not found in PATH.")
        print("     To install: pip install -r requirements-dev.txt")

def bootstrap(project_name: str, language: str, non_interactive: bool = False, install_deps: bool = False):
    root_dir = Path(__file__).parent.parent.resolve()
    print(f"🚀 Initializing AI Agent Project Template in: {root_dir}")
    print(f"   Project Name  : {project_name}")
    print(f"   Language Stack : {language}")
    print("-" * 50)
    
    check_system_dependencies()
    print("-" * 50)

    # Optionally install dev dependencies if requested
    if install_deps:
        req_file = root_dir / 'requirements-dev.txt'
        if req_file.exists():
            print("📦 Installing development dependencies from requirements-dev.txt...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req_file)], check=False)

    # 1. Update GEMINI.md
    gemini_path = root_dir / 'GEMINI.md'
    if gemini_path.exists():
        content = gemini_path.read_text(encoding='utf-8')
        content = content.replace('[Define the primary objective and business value of the project]', f'Core development for {project_name}.')
        content = content.replace('[Specify language(s): Go, Python, Rust, Java, TypeScript/Node.js, Liferay, etc.]', language.capitalize())
        gemini_path.write_text(content, encoding='utf-8')
        print(f"  ✓ Customised GEMINI.md with project name and language stack ({language})")

    # 2. Append/Update timestamps
    try:
        from append_timestamps import append_timestamps
        append_timestamps(root_dir)
        print("  ✓ Processed documentation timestamp footers")
    except Exception as e:
        print(f"  ⚠️ Warning: Could not run append_timestamps: {e}")

    # 3. Check pre-commit setup readiness
    pre_commit_config = root_dir / '.pre-commit-config.yaml'
    if pre_commit_config.exists() and shutil.which('pre-commit'):
        try:
            subprocess.run(['pre-commit', 'install'], cwd=root_dir, check=False)
            print("  ✓ Installed Git pre-commit hooks")
        except Exception as e:
            print(f"  ⚠️ Could not install pre-commit hooks: {e}")

    print("\n✅ Bootstrap completed successfully!")
    print(f"   Next step: Edit GEMINI.md to set your initial milestones, then begin coding!")

def main():
    parser = argparse.ArgumentParser(description="Bootstrap an AI Agent-assisted project.")
    parser.add_argument('--name', type=str, default='my-ai-project', help='Project name')
    parser.add_argument('--lang', type=str, default='generic', choices=SUPPORTED_LANGUAGES, help='Target language stack')
    parser.add_argument('-y', '--non-interactive', action='store_true', help='Run in non-interactive mode')
    parser.add_argument('--install-deps', action='store_true', help='Automatically pip install requirements-dev.txt')
    
    args = parser.parse_args()
    bootstrap(args.name, args.lang, args.non_interactive, args.install_deps)

if __name__ == '__main__':
    main()
