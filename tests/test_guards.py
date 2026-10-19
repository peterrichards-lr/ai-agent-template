"""
test_guards.py - Contract tests for scripts/check_guards.py and .guards.json.

Asserts that the repository passes its own guards, that a guard actually blocks
(exit 1, with file, line, reason and remedy in the output), and that an invalid
`.guards.json` fails as configuration (exit 2) rather than silently checking nothing.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / 'scripts'))

from check_guards import GUARDS_RELPATH, main  # noqa: E402

GUARD = {
    'id': 'no-todo-in-docs',
    'pattern': r'\bTODO\b',
    'include': ['docs/*.md'],
    'exclude': ['docs/allowed.md'],
    'why': 'Unfinished docs shipped twice.',
    'instead': 'File an issue and link it.',
}


def make_repo(root: Path, guards, files: dict) -> Path:
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    (root / GUARDS_RELPATH).write_text(json.dumps({'guards': guards}), encoding='utf-8')
    for relpath, content in files.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    return root


def test_repository_passes_its_own_guards():
    assert main(['--root', str(ROOT_DIR)]) == 0


def test_shipped_guards_cover_the_rules_they_replaced():
    guards = {g['id']: g for g in json.loads((ROOT_DIR / GUARDS_RELPATH).read_text())['guards']}
    assert 'no-local-file-uri-in-markdown' in guards
    assert 'no-hook-bypass-in-automation' in guards


def test_a_match_blocks_with_location_reason_and_remedy(tmp_path, capsys):
    repo = make_repo(tmp_path, [GUARD], {
        'docs/guide.md': 'Fine.\nTODO: finish\n',
        'docs/allowed.md': 'TODO is fine here\n',
        'src/notes.md': 'TODO outside include\n',
    })
    assert main(['--root', str(repo)]) == 1
    err = capsys.readouterr().err
    assert 'docs/guide.md:2: [no-todo-in-docs]' in err
    assert 'allowed.md' not in err and 'src/notes.md' not in err
    assert GUARD['why'] in err and GUARD['instead'] in err


def test_untracked_files_are_checked_but_ignored_ones_are_not(tmp_path):
    repo = make_repo(tmp_path, [GUARD], {'.gitignore': 'docs/ignored.md\n', 'docs/ignored.md': 'TODO\n'})
    assert main(['--root', str(repo)]) == 0
    (repo / 'docs' / 'new.md').write_text('TODO\n', encoding='utf-8')
    assert main(['--root', str(repo)]) == 1


def test_the_guard_config_never_matches_itself(tmp_path):
    guard = dict(GUARD, include=['*'], exclude=[])
    repo = make_repo(tmp_path, [guard], {})  # .guards.json contains the pattern text
    assert main(['--root', str(repo)]) == 0


@pytest.mark.parametrize('guards, message', [
    ('not-a-list', "'guards' list"),
    ([{k: v for k, v in GUARD.items() if k != 'why'}], 'missing why'),
    ([dict(GUARD, instead='')], 'missing instead'),
    ([GUARD, GUARD], 'duplicate guard id'),
    ([dict(GUARD, pattern='(')], 'invalid pattern'),
    ([dict(GUARD, include='docs/*.md')], 'list of glob strings'),
])
def test_invalid_config_is_a_configuration_error(tmp_path, capsys, guards, message):
    repo = make_repo(tmp_path, guards, {'docs/guide.md': 'TODO\n'})
    assert main(['--root', str(repo)]) == 2
    assert message in capsys.readouterr().err
