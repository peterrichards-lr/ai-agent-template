"""
test_skill_index.py - Contract tests for scripts/generate_skill_index.py.

The AGENTS.md skill routing table is generated from SKILL.md frontmatter, so these
tests assert two things: the committed table is exactly what the generator produces
(the drift check the hand-maintained table needed a cross-document test for), and the
generator fails loudly -- rather than silently skipping a skill -- on every input it
cannot turn into a correct row.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / 'scripts'))

from generate_skill_index import BEGIN_MARKER, END_MARKER, main  # noqa: E402

INDEX_STUB = f"# Project\n\nIntro.\n\n{BEGIN_MARKER}\nstale\n{END_MARKER}\n\nOutro.\n"


def write_skill(root: Path, directory: str, frontmatter: str) -> None:
    skill_dir = root / '.agents' / 'skills' / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(f"---\n{frontmatter}---\n\n# Body\n", encoding='utf-8')


@pytest.fixture
def repo(tmp_path):
    (tmp_path / 'AGENTS.md').write_text(INDEX_STUB, encoding='utf-8')
    write_skill(tmp_path, 'beta', "name: beta\ndescription: >-\n  Second skill,\n  folded.\n")
    write_skill(tmp_path, 'alpha', "name: alpha\ndescription: Uses a | pipe.\n")
    return tmp_path


def test_committed_agents_md_table_is_current():
    assert main(['--check', '--root', str(ROOT_DIR)]) == 0, (
        "AGENTS.md skill routing table is stale; run `make skill-index`")


def test_generates_sorted_rows_with_folded_and_escaped_descriptions(repo):
    assert main(['--root', str(repo)]) == 0
    content = (repo / 'AGENTS.md').read_text(encoding='utf-8')

    assert content.startswith('# Project\n\nIntro.\n\n') and content.endswith('\n\nOutro.\n')
    assert 'stale' not in content
    alpha = '| **[alpha](.agents/skills/alpha/SKILL.md)** | Uses a \\| pipe. |'
    beta = '| **[beta](.agents/skills/beta/SKILL.md)** | Second skill, folded. |'
    assert alpha in content and beta in content
    assert content.index(alpha) < content.index(beta)


def test_check_reports_stale_table_without_writing(repo):
    assert main(['--check', '--root', str(repo)]) == 1
    assert (repo / 'AGENTS.md').read_text(encoding='utf-8') == INDEX_STUB

    assert main(['--root', str(repo)]) == 0
    assert main(['--check', '--root', str(repo)]) == 0


@pytest.mark.parametrize('directory, frontmatter, message', [
    ('gamma', 'name: other\ndescription: Mismatch.\n', 'must equal the directory name'),
    ('gamma', 'name: gamma\n', 'description is missing'),
    ('gamma', 'name: gamma\ndescription: "   "\n', 'description is missing'),
    ('gamma', 'name: [unclosed\n', 'not valid YAML'),
])
def test_invalid_frontmatter_fails_instead_of_dropping_the_skill(repo, capsys, directory, frontmatter, message):
    write_skill(repo, directory, frontmatter)
    assert main(['--root', str(repo)]) == 2
    assert message in capsys.readouterr().err
    assert (repo / 'AGENTS.md').read_text(encoding='utf-8') == INDEX_STUB


def test_skill_directory_without_skill_md_fails(repo, capsys):
    (repo / '.agents' / 'skills' / 'empty').mkdir()
    assert main(['--root', str(repo)]) == 2
    assert 'has no SKILL.md' in capsys.readouterr().err


@pytest.mark.parametrize('document', [
    '# No markers\n',
    f'{BEGIN_MARKER}\n{BEGIN_MARKER}\n{END_MARKER}\n',
    f'{END_MARKER}\n{BEGIN_MARKER}\n',
])
def test_missing_duplicate_or_reversed_markers_fail(repo, capsys, document):
    (repo / 'AGENTS.md').write_text(document, encoding='utf-8')
    assert main(['--root', str(repo)]) == 2
    assert 'marker' in capsys.readouterr().err
    assert (repo / 'AGENTS.md').read_text(encoding='utf-8') == document


def test_no_assumptions_is_routed_as_always_active():
    """The hand-written table gave no-assumptions an 'Always' trigger; the generated row keeps it
    only because the frontmatter description says so."""
    row = next(line for line in (ROOT_DIR / 'AGENTS.md').read_text(encoding='utf-8').splitlines()
               if line.startswith('| **[no-assumptions]'))
    assert 'always' in row.lower(), row
