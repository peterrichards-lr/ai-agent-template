"""
test_task_runner.py - Makefile Task Runner & Guarded Push Suite

Covers the single entrypoint vocabulary introduced by #46:
- the root Makefile declares setup/lint/test/docs/verify/push/help and defaults to help,
- `make verify` is composed of exactly the targets CI runs, and ci.yml invokes it,
- bootstrap_template.py rewrites the language profile block per --lang,
- the Go profile exports GOTMPDIR with `:=` (the EDR-relevant variable, not -o),
- the broadened `Bash(go test*)` deny that `make test` makes safe,
- scripts/agent_push.py refuses empty pushes, unstaged trees and flag-shaped messages.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import agent_push
import bootstrap_template
from agent_push import (
    NO_VERIFY_FLAG,
    classify_worktree,
    describe_failed_hooks,
    determine_push_plan,
    upstream_tracks_this_branch,
    validate_commit_message,
)
from bootstrap_template import (
    MAKEFILE_LANGUAGE_PROFILES,
    MAKEFILE_PROFILE_BEGIN_MARKER,
    MAKEFILE_PROFILE_END_MARKER,
    MAKEFILE_RELPATH,
    SUPPORTED_LANGUAGES,
    configure_claude_settings,
    configure_task_runner,
)

REPO_ROOT = Path(__file__).parent.parent
# Spelled exactly as the file is named. macOS is case-insensitive, so a mis-cased path
# resolves locally and only fails on the Linux CI runner.
MAKEFILE = REPO_ROOT / MAKEFILE_RELPATH

VOCABULARY_TARGETS = ['setup', 'lint', 'test', 'docs', 'verify', 'push', 'help']


def read_makefile() -> str:
    return MAKEFILE.read_text(encoding='utf-8')


def run_make(*args, cwd=None):
    """Invoke make non-interactively, returning the CompletedProcess."""
    return subprocess.run(
        ['make', '--no-print-directory', *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


# --- #46: the target vocabulary itself ---------------------------------------

def test_makefile_is_shipped_at_the_repository_root():
    """Compares against the real directory entry rather than calling exists(): macOS is
    case-insensitive, so a mis-cased path passes locally and fails only on Linux CI."""
    root_entries = {entry.name for entry in REPO_ROOT.iterdir()}

    assert MAKEFILE.name in root_entries, \
        "the template must ship a root Makefile, spelled exactly, as the agent entrypoint"


@pytest.mark.parametrize('target', VOCABULARY_TARGETS)
def test_makefile_declares_every_vocabulary_target(target):
    assert re.search(rf'^{target}:', read_makefile(), re.MULTILINE), \
        f"`make {target}` is part of the fixed vocabulary and must be declared"


def test_help_is_the_default_goal():
    assert '.DEFAULT_GOAL := help' in read_makefile()


def test_make_help_lists_every_vocabulary_target():
    result = run_make('help')

    assert result.returncode == 0, result.stderr
    for target in VOCABULARY_TARGETS:
        assert f'make {target}' in result.stdout, \
            f"`make help` is the self-documenting index and must list `make {target}`"


def test_verify_is_composed_of_lint_test_and_docs():
    match = re.search(r'^verify:(.*)$', read_makefile(), re.MULTILINE)

    assert match, "verify must be declared"
    assert match.group(1).split() == ['lint', 'test', 'docs'], \
        "`make verify` must be exactly lint + test + docs so it mirrors CI"


def test_ci_runs_make_verify_rather_than_restating_the_commands():
    workflow = yaml.safe_load((REPO_ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8'))
    run_steps = [
        step.get('run', '')
        for job in workflow['jobs'].values()
        for step in job['steps']
    ]

    assert any('make verify' in step for step in run_steps), \
        "ci.yml must invoke `make verify`, otherwise local and CI gates can drift"


def test_make_verify_is_wired_to_the_documentation_helpers():
    result = run_make('-n', 'docs')

    assert result.returncode == 0, result.stderr
    assert 'scripts/append_timestamps.py' in result.stdout
    assert 'scripts/check_docs_review.py' in result.stdout


# --- #46: bootstrap fills the language profile in --------------------------

def make_marked_makefile(tmp_path: Path) -> Path:
    makefile = tmp_path / MAKEFILE_RELPATH
    makefile.write_text(
        "fixed-prologue:\n\t@echo prologue\n\n"
        f"{MAKEFILE_PROFILE_BEGIN_MARKER}\n"
        "test-lang:\n\t@echo placeholder\n"
        f"{MAKEFILE_PROFILE_END_MARKER}\n\n"
        "fixed-epilogue:\n\t@echo epilogue\n",
        encoding='utf-8',
    )
    return makefile


@pytest.mark.parametrize('language', SUPPORTED_LANGUAGES)
def test_every_supported_language_has_a_task_runner_profile(language):
    assert language in MAKEFILE_LANGUAGE_PROFILES, \
        f"--lang {language} is accepted by the CLI so it must have a Makefile profile"
    assert 'test-lang:' in MAKEFILE_LANGUAGE_PROFILES[language], \
        f"the {language} profile must define the test-lang target `make test` depends on"


@pytest.mark.parametrize('language', SUPPORTED_LANGUAGES)
def test_configure_task_runner_rewrites_only_the_marked_block(tmp_path, language):
    makefile = make_marked_makefile(tmp_path)

    assert configure_task_runner(tmp_path, language) is True

    content = makefile.read_text(encoding='utf-8')
    assert 'fixed-prologue:' in content
    assert 'fixed-epilogue:' in content
    assert '@echo placeholder' not in content
    assert MAKEFILE_LANGUAGE_PROFILES[language].strip() in content


def test_the_shipped_makefile_block_is_the_python_profile_verbatim():
    """This repository is a Python project, and the shipped block is a second copy of the
    profile bootstrap would install. Two copies drift; this test is what stops that."""
    content = read_makefile()
    begin = content.index(MAKEFILE_PROFILE_BEGIN_MARKER) + len(MAKEFILE_PROFILE_BEGIN_MARKER)
    end = content.index(MAKEFILE_PROFILE_END_MARKER)

    assert content[begin:end].strip('\n') == MAKEFILE_LANGUAGE_PROFILES['python'].strip('\n')


def test_configure_task_runner_is_idempotent(tmp_path):
    makefile = make_marked_makefile(tmp_path)

    configure_task_runner(tmp_path, 'rust')
    once = makefile.read_text(encoding='utf-8')
    configure_task_runner(tmp_path, 'rust')

    assert makefile.read_text(encoding='utf-8') == once


def test_configure_task_runner_aborts_when_the_markers_are_missing(tmp_path):
    (tmp_path / MAKEFILE_RELPATH).write_text("test:\n\t@echo hand-written\n", encoding='utf-8')

    with pytest.raises(SystemExit) as raised:
        configure_task_runner(tmp_path, 'go')

    assert raised.value.code == 1


def test_configure_task_runner_dry_run_mutates_nothing(tmp_path):
    makefile = make_marked_makefile(tmp_path)
    original = makefile.read_text(encoding='utf-8')

    assert configure_task_runner(tmp_path, 'node', dry_run=True) is True
    assert makefile.read_text(encoding='utf-8') == original


# --- #46: GOTMPDIR, not -o, decides where the unsigned binary lands ----------

def test_go_profile_exports_gotmpdir_with_immediate_assignment():
    go_profile = MAKEFILE_LANGUAGE_PROFILES['go']

    assert re.search(r'^export GOTMPDIR :=', go_profile, re.MULTILINE), \
        ("GOTMPDIR must be exported with := -- with ?= an inherited GOTMPDIR silently wins "
         "and the toolchain links outside the EDR allowlist while reporting nothing")
    assert not re.search(r'^export GOTMPDIR \?=', go_profile, re.MULTILINE)


def test_go_profile_never_runs_a_bare_go_test():
    go_profile = MAKEFILE_LANGUAGE_PROFILES['go']

    assert 'go test -c' in go_profile
    assert 'go test ./...' not in go_profile


def test_go_profile_guards_that_the_toolchain_really_links_in_the_test_dir():
    go_profile = MAKEFILE_LANGUAGE_PROFILES['go']

    assert 'go env GOTMPDIR' in go_profile, \
        "the profile must assert the resolved GOTMPDIR rather than assuming it"


def test_unit_testing_skill_teaches_the_gotmpdir_form():
    skill = (REPO_ROOT / '.agents' / 'skills' / 'unit-testing' / 'SKILL.md').read_text(encoding='utf-8')

    assert 'GOTMPDIR' in skill, \
        "the skill's Go recipe sets only -o, which is incomplete for its stated EDR purpose"
    assert 'export GOTMPDIR=' in skill or 'export GOTMPDIR :=' in skill


# --- #46: make test is what makes the wholesale go test deny safe ------------

def test_go_bootstrap_denies_go_test_wholesale(tmp_path):
    claude_dir = tmp_path / '.claude'
    claude_dir.mkdir()
    (claude_dir / 'settings.json').write_text('{"permissions": {"deny": []}}', encoding='utf-8')

    assert configure_claude_settings(tmp_path, 'go') is True

    deny = json.loads((claude_dir / 'settings.json').read_text(encoding='utf-8'))['permissions']['deny']
    assert 'Bash(go test*)' in deny, \
        "once `make test` exists the sanctioned path no longer starts with `go test`"


# --- #34 (absorbed): make push guards -----------------------------------------

def test_agent_push_never_offers_a_no_verify_bypass():
    source = (REPO_ROOT / 'scripts' / 'agent_push.py').read_text(encoding='utf-8')
    command_lines = [line for line in source.splitlines() if 'subprocess' in line or "'commit'" in line]

    assert NO_VERIFY_FLAG == '--no-verify'
    assert not any(NO_VERIFY_FLAG in line for line in command_lines), \
        "CONTRIBUTING.md forbids --no-verify; the push helper must never emit it"


def test_makefile_push_delegates_to_the_guarded_helper():
    assert 'scripts/agent_push.py' in read_makefile()


def test_makefile_attaches_the_message_so_a_flag_shaped_value_reaches_the_guard():
    """`--message $(MESSAGE)` lets a MESSAGE of "-m" be read as another option, so the
    guard never sees it and the user gets an argparse usage error instead."""
    assert '--message="$(MESSAGE)"' in read_makefile()
    assert '--message "$(MESSAGE)"' not in read_makefile()


def test_agent_push_rejects_a_flag_shaped_message_end_to_end(tmp_path):
    work = make_published_clone(tmp_path)
    (work / 'seed.txt').write_text('edited and staged\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(work), 'add', 'seed.txt'], check=True)

    result = run_agent_push(work, '--message=-m')

    assert result.returncode != 0
    assert 'looks like a command-line flag' in result.stdout + result.stderr


def test_classify_worktree_separates_staged_unstaged_and_untracked():
    porcelain = "M  staged.py\n M unstaged.py\nMM both.py\n?? scratch.txt\n"

    staged, unstaged, untracked = classify_worktree(porcelain)

    assert staged == ['staged.py', 'both.py']
    assert unstaged == ['unstaged.py', 'both.py']
    assert untracked == ['scratch.txt']


@pytest.mark.parametrize('message', ['-m', '--amend', '-', ''])
def test_flag_shaped_and_empty_commit_messages_are_rejected(message):
    error = validate_commit_message(message)

    assert error, f"{message!r} must not be accepted as a commit message subject"


def test_a_real_commit_message_is_accepted():
    assert validate_commit_message('feat(runner): add make verify') is None


def test_push_refuses_when_tracked_changes_are_modified_but_unstaged():
    ok, reason = determine_push_plan(
        staged=['a.py'], unstaged=['b.py'], unpushed_count=0, message='feat: a')

    assert ok is False
    assert 'b.py' in reason


def test_push_refuses_a_no_op_push():
    ok, reason = determine_push_plan(
        staged=[], unstaged=[], unpushed_count=0, message=None)

    assert ok is False
    assert 'nothing' in reason.lower()


def test_push_allows_pushing_already_committed_work_without_a_message():
    ok, reason = determine_push_plan(
        staged=[], unstaged=[], unpushed_count=2, message=None)

    assert ok is True, reason


def test_push_requires_a_message_when_something_is_staged():
    ok, reason = determine_push_plan(
        staged=['a.py'], unstaged=[], unpushed_count=0, message=None)

    assert ok is False
    assert 'MESSAGE' in reason


def test_failed_pre_commit_hooks_are_named_with_the_targeted_skip_form():
    output = (
        "Append Markdown Timestamps.....Passed\n"
        "Check Documentation Review Staleness.....Failed\n"
        "- hook id: check-docs-review\n"
        "- exit code: 1\n"
    )

    guidance = describe_failed_hooks(output)

    assert 'check-docs-review' in guidance
    assert 'SKIP=check-docs-review' in guidance


@pytest.mark.parametrize('upstream,branch,tracks', [
    (None, 'feat/46-90-task-runner', False),
    # `git checkout -b topic origin/main` -- the standard start -- leaves the upstream
    # pointing at a differently named branch, and a bare `git push` then aborts.
    ('origin/main', 'feat/46-90-task-runner', False),
    ('origin/feat/46-90-task-runner', 'feat/46-90-task-runner', True),
    ('upstream/main', 'main', True),
])
def test_upstream_is_only_trusted_when_it_names_this_branch(upstream, branch, tracks):
    assert upstream_tracks_this_branch(upstream, branch) is tracks


def test_agent_push_sets_upstream_when_the_branch_was_started_from_another(tmp_path):
    work = make_published_clone(tmp_path)
    subprocess.run(['git', '-C', str(work), 'checkout', '-q', '-b', 'topic',
                    '--track', 'origin/' + current_branch_of(work)], check=True)
    (work / 'seed.txt').write_text('topic work\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(work), 'add', 'seed.txt'], check=True)
    subprocess.run(['git', '-C', str(work), 'commit', '-qm', 'topic', '--no-verify'], check=True)

    result = run_agent_push(work)

    assert result.returncode == 0, result.stdout + result.stderr
    assert '--set-upstream origin topic' in result.stdout, \
        "a bare `git push` aborts when the upstream names a different branch"


def test_agent_push_still_refuses_a_no_op_on_a_branch_with_a_mismatched_upstream(tmp_path):
    """Pins the rev-list argument order: `--not --remotes HEAD` negates HEAD as well, so
    the count is 0 whatever the branch contains and the no-op guard passes vacuously."""
    work = make_published_clone(tmp_path)
    subprocess.run(['git', '-C', str(work), 'checkout', '-q', '-b', 'topic',
                    '--track', 'origin/' + current_branch_of(work)], check=True)

    result = run_agent_push(work)

    assert result.returncode != 0
    assert 'nothing' in (result.stdout + result.stderr).lower()


def test_agent_push_runs_the_attribution_guard_before_committing():
    assert agent_push.ATTRIBUTION_SCRIPT_RELPATH.as_posix() == 'scripts/check_commit_attribution.py'


def current_branch_of(work: Path) -> str:
    return subprocess.run(['git', '-C', str(work), 'rev-parse', '--abbrev-ref', 'HEAD'],
                          capture_output=True, text=True, check=True).stdout.strip()


def make_published_clone(tmp_path: Path) -> Path:
    """A working clone whose branch is fully pushed: staged and unpushed are both empty."""
    origin = tmp_path / 'origin.git'
    work = tmp_path / 'work'
    subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True)
    subprocess.run(['git', 'init', '-q', str(work)], check=True)
    for key, value in (('user.email', '1+test@users.noreply.github.com'), ('user.name', 'Test')):
        subprocess.run(['git', '-C', str(work), 'config', key, value], check=True)
    (work / 'seed.txt').write_text('seed\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(work), 'add', 'seed.txt'], check=True)
    subprocess.run(['git', '-C', str(work), 'commit', '-qm', 'seed', '--no-verify'], check=True)
    subprocess.run(['git', '-C', str(work), 'remote', 'add', 'origin', str(origin)], check=True)
    branch = subprocess.run(['git', '-C', str(work), 'rev-parse', '--abbrev-ref', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(['git', '-C', str(work), 'push', '-q', '-u', 'origin', branch], check=True)
    return work


def run_agent_push(work: Path, *args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / 'scripts' / 'agent_push.py'), '--dry-run', *args],
        cwd=str(work), capture_output=True, text=True, check=False)


def test_agent_push_refuses_an_empty_push_end_to_end(tmp_path):
    result = run_agent_push(make_published_clone(tmp_path))

    assert result.returncode != 0, "an empty push reported as success is the #34 failure mode"
    assert 'nothing' in (result.stdout + result.stderr).lower()


def test_agent_push_refuses_an_unstaged_tree_end_to_end(tmp_path):
    work = make_published_clone(tmp_path)
    (work / 'seed.txt').write_text('edited but never staged\n', encoding='utf-8')

    result = run_agent_push(work, '--message', 'feat: edit the seed')

    assert result.returncode != 0
    assert 'seed.txt' in result.stdout + result.stderr


def test_agent_push_accepts_a_staged_change_with_a_real_message_end_to_end(tmp_path):
    work = make_published_clone(tmp_path)
    (work / 'seed.txt').write_text('edited and staged\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(work), 'add', 'seed.txt'], check=True)

    result = run_agent_push(work, '--message', 'feat: edit the seed')

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'git push' in result.stdout


# --- #46: the scattered restatements collapse to the vocabulary --------------

def test_agents_rule_five_documents_the_task_runner_vocabulary():
    agents = (REPO_ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    rule_five = agents.split('### 5. Primary Unit Testing Command')[1].split('### 6.')[0]

    for target in VOCABULARY_TARGETS:
        assert f'`make {target}`' in rule_five, \
            f"rule 5 is where agents look for the command that gates completion; it must name `make {target}`"


@pytest.mark.parametrize('language', SUPPORTED_LANGUAGES)
def test_bootstrap_substitutes_the_task_runner_verb_not_an_ecosystem_command(tmp_path, language):
    """Five copies of each ecosystem's command collapse to one: the Makefile."""
    agents_md = tmp_path / 'AGENTS.md'
    agents_md.write_text(
        "Primary Unit Testing Command: `<TEST_COMMAND_PLACEHOLDER>`\n", encoding='utf-8')

    bootstrap_template.configure_language_profile(tmp_path, language)

    assert agents_md.read_text(encoding='utf-8').strip() == 'Primary Unit Testing Command: `make test`'


def test_contributing_pull_request_protocol_uses_the_vocabulary():
    contributing = (REPO_ROOT / 'CONTRIBUTING.md').read_text(encoding='utf-8')
    protocol = contributing.split('## 3. Pull Request Protocol')[1].split('## 4.')[0]

    assert 'make verify' in protocol
    assert 'cargo test' not in protocol
    assert 'npm test' not in protocol


def test_template_guide_language_sections_defer_to_the_task_runner():
    guide = (REPO_ROOT / 'docs' / 'TEMPLATE_GUIDE.md').read_text(encoding='utf-8')
    customization = guide.split('## Language Customization Guide')[1].split('## Included Skill Modules')[0]

    assert 'make test' in customization
    assert 'cargo test --quiet' not in customization
    assert 'npm test -- --ci' not in customization


def test_readme_documents_the_windows_make_limitation():
    readme = (REPO_ROOT / 'README.md').read_text(encoding='utf-8')

    assert 'make verify' in readme
    assert re.search(r'Windows.*Make|Make.*Windows', readme), \
        "Make is not present by default on Windows; the limitation is accepted and documented"
