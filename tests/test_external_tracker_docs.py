"""
test_external_tracker_docs.py - Contract tests for the canonical-tracker rule and
the external-tracker escape hatch documented in `.agents/skills/github-workflow/SKILL.md`.

Three of this template's sibling repositories run a second tracker (Jira) alongside
GitHub Issues, and each solved the same problem privately. The template's job is a
sound default plus a documented escape hatch, so these tests assert:

1. The canonical-tracker rule is about having *one* tracker, not about which one.
2. The external-tracker pattern answers the three questions those repos each had to
   answer: how external IDs are referenced, which tracker is authoritative for what,
   and how the two are kept from drifting.
3. The guidance is provider-agnostic -- Jira is an instance of the pattern, not the
   pattern itself.
4. The `Closes #N` link gate's limitation is named in the docs rather than papered
   over -- and `test_link_gate_only_understands_github_issue_numbers` holds the
   documented claim to the checker's actual behaviour, so building a configurable
   ID pattern later cannot silently leave the docs lying.

Kept out of tests/test_template_scripts.py, which covers scripts/ behaviour and the
cross-document skill-name drift check.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from check_closing_refs import validate_pr_closing_refs  # noqa: E402

GITHUB_WORKFLOW_SKILL = REPO_ROOT / '.agents' / 'skills' / 'github-workflow' / 'SKILL.md'
AGENTS_MD = REPO_ROOT / 'AGENTS.md'
TEMPLATE_GUIDE = REPO_ROOT / 'docs' / 'TEMPLATE_GUIDE.md'
FEATURE_REQUEST_FORM = REPO_ROOT / '.github' / 'ISSUE_TEMPLATE' / 'feature_request.yml'

ISSUE_LINK_WORKFLOW_RELPATH = '.github/workflows/issue-link-check.yml'
CLOSING_REF_SCRIPT_RELPATH = 'scripts/check_closing_refs.py'

# Providers the pattern must generalise over. Naming several of them is what keeps
# the section from silently becoming a Jira-only appendix.
EXAMPLE_TRACKERS = ('jira', 'linear', 'azure boards', 'youtrack', 'shortcut', 'bugzilla')

SECTION_HEADING_REGEX = re.compile(r'(?m)^###\s+(.+)$')


def skill_text() -> str:
    return GITHUB_WORKFLOW_SKILL.read_text(encoding='utf-8')


def skill_section(heading_fragment: str) -> str:
    """Return the body of the first `### ` section whose heading contains the fragment."""
    text = skill_text()
    headings = list(SECTION_HEADING_REGEX.finditer(text))
    for index, match in enumerate(headings):
        if heading_fragment.lower() in match.group(1).lower():
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            return text[match.start():end]
    raise AssertionError(
        f"{GITHUB_WORKFLOW_SKILL} has no '### ' section whose heading contains {heading_fragment!r}"
    )


def test_canonical_tracker_rule_is_about_one_tracker_not_about_github():
    """Rule 4 must state the invariant that matters: one tracker per repo, GitHub by default."""
    section = skill_section('Technical Debt Issue Creation').lower()

    assert 'one canonical tracker per repo' in section, (
        "Rule 4 must state the invariant as 'one canonical tracker per repo', not as a "
        "GitHub Issues-specific mandate"
    )
    assert 'defaulting to github issues' in section, (
        "Rule 4 must name GitHub Issues as the default so the template still ships an opinion"
    )
    assert 'external tracker' in section, (
        "Rule 4 must point at the external-tracker section instead of forbidding a second "
        "tracker outright"
    )


def test_external_tracker_section_answers_the_three_load_bearing_questions():
    """The pattern is only useful if it settles referencing, authority, and drift."""
    section = skill_section('External Tracker')
    lowered = section.lower()

    assert 'commit' in lowered and ('pull request' in lowered or 'pr body' in lowered), (
        "The external-tracker section must say how external IDs are referenced in commits "
        "and pull requests"
    )
    assert 'authoritative' in lowered, (
        "The external-tracker section must say which tracker is authoritative for what"
    )
    assert 'drift' in lowered, (
        "The external-tracker section must say how the two trackers are kept from drifting"
    )
    assert 'mirror' in lowered, (
        "The external-tracker section must describe the one-directional mirror the sibling "
        "repos converged on, rather than implying two-way sync"
    )


def test_external_tracker_guidance_is_provider_agnostic():
    """Jira is the instance the sibling repos happen to run, not the abstraction."""
    section = skill_section('External Tracker')
    heading = section.splitlines()[0].lower()

    assert 'jira' not in heading, (
        f"External-tracker heading {heading!r} must not be named after a single provider"
    )

    lowered = section.lower()
    named = [tracker for tracker in EXAMPLE_TRACKERS if tracker in lowered]
    assert len(named) >= 3, (
        "The external-tracker section must name at least three example trackers so the "
        f"pattern reads as provider-agnostic; found: {named}"
    )


def test_docs_name_the_link_gate_constraint_instead_of_hiding_it():
    """The `Closes #N` gate's cost for external-tracker repos must be stated plainly."""
    section = skill_section('External Tracker')

    assert ISSUE_LINK_WORKFLOW_RELPATH in section, (
        f"The external-tracker section must name {ISSUE_LINK_WORKFLOW_RELPATH} as the gate "
        "that only understands GitHub issue numbers"
    )
    assert CLOSING_REF_SCRIPT_RELPATH in section, (
        f"The external-tracker section must name {CLOSING_REF_SCRIPT_RELPATH} as the gate "
        "that only understands GitHub issue numbers"
    )

    lowered = section.lower()
    assert 'remains mandatory' in lowered, (
        "The external-tracker section must state plainly that a GitHub issue remains "
        "mandatory for the link gate regardless of where planning happens"
    )
    assert 'no-issue-needed' in lowered, (
        "The external-tracker section must name the existing escape hatch label rather than "
        "implying a new one is needed"
    )


def test_link_gate_only_understands_github_issue_numbers():
    """Holds the documented limitation to the checker's real behaviour.

    The docs claim a repo whose canonical tracker is external must still open a GitHub
    issue to satisfy the gate. If `check_closing_refs.py` ever learns a configurable ID
    pattern, this test fails and the claim has to be rewritten rather than left stale.
    """
    external_key_body = "## Linked Issue\n\nCloses PROJ-123\n"
    is_valid, violations = validate_pr_closing_refs("docs: external tracker", external_key_body)
    assert is_valid is False, (
        "check_closing_refs.py accepted an external tracker key; the documented limitation "
        "in github-workflow/SKILL.md is now false and must be rewritten"
    )
    assert violations, "A rejected PR body must explain why it was rejected"

    github_body = "## Linked Issue\n\nCloses #60\n"
    assert validate_pr_closing_refs("docs: external tracker", github_body)[0] is True, (
        "A plain GitHub closing reference must still pass the gate"
    )


def test_core_docs_surface_the_external_tracker_escape_hatch():
    """An agent reading AGENTS.md or the guide must be able to find the escape hatch."""
    agents_text = AGENTS_MD.read_text(encoding='utf-8').lower()
    assert 'canonical tracker' in agents_text, (
        "AGENTS.md must describe tech-debt tracking in terms of the repo's canonical tracker"
    )
    assert 'external tracker' in agents_text, (
        "AGENTS.md must point at the external-tracker rule for repos that run a second tracker"
    )

    guide_text = TEMPLATE_GUIDE.read_text(encoding='utf-8').lower()
    assert 'external tracker' in guide_text, (
        "docs/TEMPLATE_GUIDE.md must mention the external-tracker escape hatch"
    )


def test_feature_request_form_invites_a_reaction_as_the_demand_signal():
    """Salvaged from the closed reaction-triage issue: voting is a reaction, not a '+1' comment."""
    form_text = FEATURE_REQUEST_FORM.read_text(encoding='utf-8')

    assert '\U0001F44D' in form_text, (
        "feature_request.yml must invite the 👍 reaction as the demand signal"
    )
    assert '"+1"' in form_text, (
        "feature_request.yml must steer contributors away from '+1' comments, which push the "
        "discussion down without registering a vote"
    )
