#!/usr/bin/env python3
"""
generate_skill_index.py - Generate the AGENTS.md skill routing table from SKILL.md frontmatter.

The routing table used to be maintained by hand in AGENTS.md, restated in
docs/TEMPLATE_GUIDE.md and again in the README tree, with a test asserting the three
copies agreed with the directories on disk. Each new skill meant editing four places
and the test only noticed a missing *name*, never a stale description.

The frontmatter of each `.agents/skills/<name>/SKILL.md` is now the single owner of a
skill's name and description -- it is also what agent harnesses load eagerly -- and
this script renders the one routing table from it, between the markers below. The
other documents point at AGENTS.md instead of restating it.

Usage:
  python3 scripts/generate_skill_index.py           # rewrite the table in place
  python3 scripts/generate_skill_index.py --check   # exit 1 if the table is stale

Exit codes:
  0  table is current (or was rewritten)
  1  --check found a stale table
  2  a skill's frontmatter or the AGENTS.md markers are invalid
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

SKILLS_RELPATH = Path('.agents') / 'skills'
INDEX_RELPATH = Path('AGENTS.md')
BEGIN_MARKER = '<!-- BEGIN GENERATED: skill-index (scripts/generate_skill_index.py) -->'
END_MARKER = '<!-- END GENERATED: skill-index -->'
REGENERATE_HINT = 'Run `make skill-index` (python3 scripts/generate_skill_index.py) and commit the result.'


class SkillIndexError(Exception):
    """A skill or the index document cannot be parsed into a routing table."""


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    relpath: str


def parse_skill(skill_dir: Path, root_dir: Path) -> Skill:
    """Parse one skill directory, failing on anything the harness would also reject."""
    skill_file = skill_dir / 'SKILL.md'
    relpath = skill_file.relative_to(root_dir).as_posix()
    if not skill_file.is_file():
        raise SkillIndexError(f"{skill_dir.relative_to(root_dir).as_posix()}/ has no SKILL.md")

    content = skill_file.read_text(encoding='utf-8')
    parts = content.split('---\n', 2)
    if not content.startswith('---\n') or len(parts) < 3:
        raise SkillIndexError(f"{relpath}: missing YAML frontmatter delimited by '---' lines")

    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as error:
        raise SkillIndexError(f"{relpath}: frontmatter is not valid YAML: {error}") from error
    if not isinstance(frontmatter, dict):
        raise SkillIndexError(f"{relpath}: frontmatter must be a mapping")

    name = frontmatter.get('name')
    if name != skill_dir.name:
        raise SkillIndexError(
            f"{relpath}: frontmatter name {name!r} must equal the directory name {skill_dir.name!r}")

    description = frontmatter.get('description')
    if not isinstance(description, str) or not description.strip():
        raise SkillIndexError(f"{relpath}: frontmatter description is missing or empty")

    return Skill(name=name, description=' '.join(description.split()), relpath=relpath)


def discover_skills(root_dir: Path) -> list:
    skills_dir = root_dir / SKILLS_RELPATH
    if not skills_dir.is_dir():
        raise SkillIndexError(f"{SKILLS_RELPATH.as_posix()}/ not found")
    skill_dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir())
    if not skill_dirs:
        raise SkillIndexError(f"{SKILLS_RELPATH.as_posix()}/ contains no skills")
    return [parse_skill(d, root_dir) for d in skill_dirs]


def render_table(skills: list) -> str:
    rows = [
        '| Skill | When to load and what it governs |',
        '| :--- | :--- |',
    ]
    for skill in skills:
        # A literal pipe would end the cell early (documentation's footer format has one).
        description = skill.description.replace('|', '\\|')
        rows.append(f"| **[{skill.name}]({skill.relpath})** | {description} |")
    return '\n'.join(rows)


def replace_generated_block(document: str, table: str) -> str:
    begin_count = document.count(BEGIN_MARKER)
    end_count = document.count(END_MARKER)
    if begin_count != 1 or end_count != 1:
        raise SkillIndexError(
            f"{INDEX_RELPATH} must contain exactly one begin and one end marker "
            f"(found {begin_count} and {end_count}):\n  {BEGIN_MARKER}\n  {END_MARKER}")
    head, rest = document.split(BEGIN_MARKER)
    if END_MARKER not in rest:
        raise SkillIndexError(f"{INDEX_RELPATH}: the end marker precedes the begin marker")
    _, tail = rest.split(END_MARKER)
    return f"{head}{BEGIN_MARKER}\n{table}\n{END_MARKER}{tail}"


def run(root_dir: Path, check: bool) -> int:
    try:
        skills = discover_skills(root_dir)
        index_path = root_dir / INDEX_RELPATH
        if not index_path.is_file():
            raise SkillIndexError(f"{INDEX_RELPATH} not found")
        current = index_path.read_text(encoding='utf-8')
        expected = replace_generated_block(current, render_table(skills))
    except SkillIndexError as error:
        print(f"❌ Skill index: {error}", file=sys.stderr)
        return 2

    if current == expected:
        print(f"✓ {INDEX_RELPATH} skill routing table is current ({len(skills)} skills).")
        return 0
    if check:
        print(f"❌ {INDEX_RELPATH} skill routing table is stale. {REGENERATE_HINT}", file=sys.stderr)
        return 1
    index_path.write_text(expected, encoding='utf-8')
    print(f"  ✓ Regenerated the {INDEX_RELPATH} skill routing table ({len(skills)} skills).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--check', action='store_true',
                        help='report a stale table instead of rewriting it')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent,
                        help='repository root (default: this script\'s repository)')
    args = parser.parse_args(argv)
    return run(args.root.resolve(), args.check)


if __name__ == '__main__':
    sys.exit(main())
