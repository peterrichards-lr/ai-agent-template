"""
test_bootstrap_flags.py - Bootstrap CLI Surface Suite (#90)

`-y` / `--non-interactive` existed on a script with no `input()` prompt, and was
quietly overloaded as a second trigger for template cleanup:

    if clean_template or non_interactive:
        clean_template_meta_docs(...)

So the conventional "do not prompt me" flag deleted docs/TEMPLATE_GUIDE.md, tests/
and src/__init__.py. These tests pin the flag out of existence and prove that
cleanup is reachable only through the explicit --clean-template switch.
"""

import ast
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from bootstrap_template import bootstrap, build_arg_parser

REPO_ROOT = Path(__file__).parent.parent
BOOTSTRAP_SCRIPT = REPO_ROOT / 'scripts' / 'bootstrap_template.py'

CLEANUP_BANNER = 'Cleaning template-specific meta documentation'

REQUIRED_ARGS = [
    '--name', 'flag-probe',
    '--repo-owner', 'flag-probe-org',
    '--conduct-email', 'conduct@example.com',
]


def run_bootstrap(*extra_args):
    """Run the bootstrapper as a subprocess. Always --dry-run: nothing is mutated."""
    return subprocess.run(
        [sys.executable, str(BOOTSTRAP_SCRIPT), *REQUIRED_ARGS, '--dry-run', *extra_args],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )


def test_the_bootstrapper_never_calls_input():
    """Parsed rather than grepped, so a comment about input() is not mistaken for a call."""
    tree = ast.parse(BOOTSTRAP_SCRIPT.read_text(encoding='utf-8'))
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert 'input' not in called_names, \
        "a --non-interactive flag can only be honest if there is an interactive mode"


def test_parser_no_longer_exposes_a_non_interactive_flag():
    option_strings = {
        option
        for action in build_arg_parser()._actions
        for option in action.option_strings
    }

    assert '-y' not in option_strings
    assert '--non-interactive' not in option_strings


def test_bootstrap_no_longer_accepts_a_non_interactive_parameter():
    assert 'non_interactive' not in inspect.signature(bootstrap).parameters


def test_passing_y_fails_at_parse_time_before_any_file_is_touched():
    result = run_bootstrap('-y')

    assert result.returncode == 2, "argparse must reject the removed flag as a usage error"
    assert 'unrecognized arguments' in result.stderr
    assert CLEANUP_BANNER not in result.stdout, \
        "-y must never reach template cleanup -- that is the #90 destruction path"


def test_cleanup_does_not_run_without_clean_template():
    result = run_bootstrap()

    assert result.returncode == 0, result.stderr
    assert CLEANUP_BANNER not in result.stdout
    assert 'docs/TEMPLATE_GUIDE.md' not in result.stdout


def test_clean_template_remains_the_explicit_way_to_request_cleanup():
    result = run_bootstrap('--clean-template')

    assert result.returncode == 0, result.stderr
    assert CLEANUP_BANNER in result.stdout
    assert 'docs/TEMPLATE_GUIDE.md' in result.stdout


def test_changelog_records_the_removal_as_a_behaviour_change():
    changelog = (REPO_ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')

    assert '--non-interactive' in changelog, \
        "removing the flag is a behaviour change for anyone relying on -y to clean"
