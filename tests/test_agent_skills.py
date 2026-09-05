"""
test_agent_skills.py - Content contract tests for `.agents/skills/` skill files.

Separate from test_template_scripts.py (which covers scripts/ behaviour and the
cross-document skill-name drift check). This module asserts the *substance* of
individual skill files: that the always-active anti-hallucination skill states
its operative clauses, that the end-to-end verification skill covers each branch
it is required to cover, and that the documents pointing at them stay in sync.
"""

import re
import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).parent.parent

# Add scripts directory to import path (mirrors tests/test_template_scripts.py)
sys.path.insert(0, str(ROOT_DIR / 'scripts'))

SKILLS_DIR = ROOT_DIR / '.agents' / 'skills'
DESCRIPTION_MIN_WORDS = 20
DESCRIPTION_MAX_WORDS = 25


def read_skill(skill_name):
    """Return (frontmatter dict, body text) for a skill, lowercased body."""
    skill_file = SKILLS_DIR / skill_name / 'SKILL.md'
    assert skill_file.exists(), f"Missing skill file {skill_file}"
    content = skill_file.read_text(encoding='utf-8')
    parts = content.split('---\n', 2)
    assert len(parts) >= 3, f"{skill_file} invalid frontmatter structure"
    frontmatter = yaml.safe_load(parts[1])
    return frontmatter, parts[2]


def assert_concise_description(frontmatter, skill_name):
    """Descriptions are loaded eagerly by the agent harness, so they stay short."""
    assert frontmatter.get('name') == skill_name
    word_count = len(frontmatter.get('description', '').split())
    assert DESCRIPTION_MIN_WORDS <= word_count <= DESCRIPTION_MAX_WORDS, (
        f"{skill_name} description is {word_count} words; "
        f"expected {DESCRIPTION_MIN_WORDS}-{DESCRIPTION_MAX_WORDS}"
    )


def test_no_assumptions_skill_states_current_session_evidence_rule():
    frontmatter, body = read_skill('no-assumptions')
    assert_concise_description(frontmatter, 'no-assumptions')

    description = frontmatter['description'].lower()
    assert 'always' in description, "no-assumptions description must declare the skill always active"

    lowered = body.lower()
    assert 'current session' in lowered, "Missing the operative current-session evidence clause"
    assert 'compaction' in lowered, "Missing the context-compaction corollary"
    assert 'resume' in lowered, "Missing the session-resume corollary"
    assert 'cannot be waived' in lowered, "Missing the non-waivable statement"


def test_agents_md_rule_one_is_a_pointer_to_the_no_assumptions_skill():
    agents_content = (ROOT_DIR / 'AGENTS.md').read_text(encoding='utf-8')
    section = re.search(
        r'### 1\. Anti-Hallucination Protocol\n(.*?)\n### 2\.',
        agents_content,
        re.DOTALL,
    )
    assert section, "AGENTS.md universal rule 1 (Anti-Hallucination Protocol) not found"

    prose_lines = [line for line in section.group(1).splitlines() if line.strip()]
    assert len(prose_lines) == 1, (
        "Rule 1 must be a one-line pointer so the skill file stays the single source "
        f"of truth; found {len(prose_lines)} prose lines"
    )
    assert 'no-assumptions/SKILL.md' in prose_lines[0], "Rule 1 must point at no-assumptions/SKILL.md"


def test_e2e_verification_skill_covers_every_required_branch():
    frontmatter, body = read_skill('e2e-verification')
    assert_concise_description(frontmatter, 'e2e-verification')

    lowered = body.lower()

    # 1. Decision rule for when unit tests are insufficient evidence.
    for trigger in ['rendering', 'process or network boundary', 'cli', 'deployment']:
        assert trigger in lowered, f"Decision rule missing insufficiency trigger '{trigger}'"

    # 2. What counts as evidence, and what explicitly does not.
    for evidence in ['screenshot', 'transcript', 'http response', 'log line']:
        assert evidence in lowered, f"Evidence catalogue missing '{evidence}'"
    assert 'is not evidence' in lowered, (
        "Must state explicitly that a passing unit test on the new code path "
        "is not evidence the system works"
    )

    # 3. Non-interactive execution and teardown.
    assert 'non-interactive' in lowered
    assert 'tear down' in lowered or 'teardown' in lowered

    # 4. Escalation to a human, with a concrete pass criterion rather than "please verify".
    assert 'human-in-the-loop/SKILL.md' in body, "Missing escalation cross-reference"
    assert 'please verify' in lowered, "Must name the vague 'please verify' anti-pattern it replaces"


def test_unit_testing_stopping_condition_defers_to_e2e_verification():
    _, body = read_skill('unit-testing')
    assert 'e2e-verification/SKILL.md' in body, (
        "unit-testing must cross-reference e2e-verification so its stopping condition "
        "is the appropriate verification, not merely a green suite"
    )
    assert 'appropriate verification' in body.lower(), (
        "unit-testing rule 3 must read as 'the appropriate verification for this change'"
    )


def test_both_new_skills_are_routed_in_every_index_document():
    agents_content = (ROOT_DIR / 'AGENTS.md').read_text(encoding='utf-8')
    guide_content = (ROOT_DIR / 'docs' / 'TEMPLATE_GUIDE.md').read_text(encoding='utf-8')
    readme_content = (ROOT_DIR / 'README.md').read_text(encoding='utf-8')

    for skill_name in ('no-assumptions', 'e2e-verification'):
        assert (SKILLS_DIR / skill_name / 'SKILL.md').exists()
        assert f'**[{skill_name}]' in agents_content, f"AGENTS.md routing table missing {skill_name}"
        assert f'**`{skill_name}`**' in guide_content, f"TEMPLATE_GUIDE.md table missing {skill_name}"
        assert re.search(rf'[├└]──\s+{skill_name}/', readme_content), (
            f"README.md skills tree missing {skill_name}"
        )

    routing_row = re.search(r'^\|\s*\*\*\[no-assumptions\].*$', agents_content, re.MULTILINE)
    assert routing_row, "no-assumptions routing row not found"
    assert 'always' in routing_row.group(0).lower(), (
        "no-assumptions must be routed with an 'always' trigger condition"
    )
