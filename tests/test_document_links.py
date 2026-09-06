"""
test_document_links.py - Link-target contract for the Markdown this template ships.

`AGENTS.md`'s skill routing table linked every `SKILL.md` twice -- once on the skill
name, once on the path -- with an absolute `file:///.agents/skills/<name>/SKILL.md`
URI, from the initial commit onwards. That URI resolves to `/.agents/skills/...` on
the filesystem root rather than to the path inside the repository, so all 26 links
pointed at a file on nobody's machine; and GitHub's Markdown renderer permits only a
small set of URI schemes, so on github.com they degraded to unclickable text and the
routing table lost the navigation it exists to provide (#110).

Two assertions, deliberately separate:

1. every routing-table link must resolve to a file that is actually in the
   repository -- the property the table is for, asserted positively rather than by
   spelling out the URI scheme that happened to break it; and
2. no shipped Markdown may carry a local-file URI at all -- the guard, since every skill
   row added since the initial commit copied the pattern from the row above it, and
   nothing stopped the next one doing the same.

The second assertion is deliberately absolute rather than exempting code spans: no
shipped document has needed to quote the scheme, and an exemption is a hole in a guard
whose whole job is to stop the string reappearing. A document that must discuss it names
it descriptively, as CHANGELOG.md's entry for #110 does.

Kept out of tests/test_template_scripts.py, which covers `scripts/` behaviour and the
cross-document skill-name drift check, and whose routing-table parsing keys on the
bold link *text* (`**[<name>]`) and is indifferent to the link target.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / 'AGENTS.md'

# A routing-table row opens with the skill name as a bold link: `| **[no-assumptions](...)`.
ROUTING_TABLE_ROW_PREFIX = '| **['
MARKDOWN_LINK_TARGET = re.compile(r'\]\(([^)]+)\)')

# Assembled rather than written out, so this file can name the scheme it forbids
# without tripping a future guard that scans the repository rather than its Markdown.
LOCAL_FILE_URI_SCHEME = 'file' + '://'


def shipped_markdown_files():
    """Every Markdown file delivered with the template, each visited once.

    `.claude/` is skipped whole: its only tracked entries are `settings.json` and the
    `skills` symlink onto `.agents/skills`, which is scanned at its real path, and a
    developer's local git worktrees live under `.claude/worktrees/`.
    """
    for markdown_path in sorted(REPO_ROOT.rglob('*.md')):
        relative_path = markdown_path.relative_to(REPO_ROOT).as_posix()
        if relative_path.startswith('.claude/') or relative_path.startswith('.git/'):
            continue
        yield relative_path, markdown_path


def routing_table_link_targets(agents_content):
    """Link targets from every row of the AGENTS.md skill routing table."""
    targets = []
    for line in agents_content.splitlines():
        if line.startswith(ROUTING_TABLE_ROW_PREFIX):
            targets.extend(MARKDOWN_LINK_TARGET.findall(line))
    return targets


def test_every_skill_routing_link_resolves_to_a_file_in_the_repository():
    targets = routing_table_link_targets(AGENTS_MD.read_text(encoding='utf-8'))
    assert targets, "no links found in the AGENTS.md skill routing table"

    unresolved = [target for target in targets if not (REPO_ROOT / target).is_file()]
    assert unresolved == [], f"AGENTS.md routing links resolving to no file: {unresolved}"


def test_the_routing_table_links_both_the_name_and_the_path_of_every_skill():
    skill_dirs = [d for d in (REPO_ROOT / '.agents' / 'skills').iterdir() if d.is_dir()]
    targets = routing_table_link_targets(AGENTS_MD.read_text(encoding='utf-8'))

    assert len(targets) == 2 * len(skill_dirs), (
        f"expected two links per skill row ({2 * len(skill_dirs)}), found {len(targets)}")


def test_no_shipped_markdown_uses_a_local_file_uri_scheme():
    offenders = []
    for relative_path, markdown_path in shipped_markdown_files():
        for line_number, line in enumerate(
                markdown_path.read_text(encoding='utf-8').splitlines(), start=1):
            if LOCAL_FILE_URI_SCHEME in line:
                offenders.append(f"{relative_path}:{line_number}")

    assert offenders == [], (
        f"{LOCAL_FILE_URI_SCHEME} links resolve to the filesystem root and are dropped by "
        f"GitHub's renderer; use a repository-relative path instead: {offenders}")
