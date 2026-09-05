"""
test_issue_templates.py - Structural tests for the GitHub Issue Forms.

Covers .github/ISSUE_TEMPLATE/*.yml: valid issue-form schema, the canonical
tech-debt category taxonomy (form is the single source of truth), the cap on
required fields, and the agent-facing filing instructions in
.agents/skills/github-workflow/SKILL.md that must stay in step with the forms.

Kept separate from test_template_scripts.py, which tests scripts/ rather than
repository metadata files.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
ISSUE_TEMPLATE_DIR = REPO_ROOT / '.github' / 'ISSUE_TEMPLATE'
GITHUB_WORKFLOW_SKILL = REPO_ROOT / '.agents' / 'skills' / 'github-workflow' / 'SKILL.md'
TEMPLATE_GUIDE = REPO_ROOT / 'docs' / 'TEMPLATE_GUIDE.md'

TECH_DEBT_FORM_RELPATH = '.github/ISSUE_TEMPLATE/tech_debt.yml'
GITHUB_WORKFLOW_SKILL_RELPATH = '.agents/skills/github-workflow/SKILL.md'

# Filename -> (expected labels, expected title prefix) carried over from the
# legacy Markdown templates so downstream triage automation keeps working.
EXPECTED_FORMS = {
    'bug_report.yml': (['bug'], 'fix: '),
    'feature_request.yml': (['enhancement'], 'feat: '),
    'tech_debt.yml': (['tech-debt'], 'Tech Debt: '),
}

LEGACY_MARKDOWN_TEMPLATES = ['bug.md', 'feature.md', 'tech_debt.md']

# A form that demands a long list of mandatory fields gets routed around rather
# than filled in, so the required set is capped rather than merely reviewed.
MAX_REQUIRED_FIELDS_PER_FORM = 4

INPUT_ELEMENT_TYPES = {'input', 'textarea', 'dropdown', 'checkboxes'}
ALL_ELEMENT_TYPES = INPUT_ELEMENT_TYPES | {'markdown'}

# Distinctive member of the taxonomy, used to detect unauthorised extra copies.
TAXONOMY_MARKER = 'Deprecated Patterns'
TAXONOMY_CANONICAL_FILES = {TECH_DEBT_FORM_RELPATH, GITHUB_WORKFLOW_SKILL_RELPATH}

SKILL_CATEGORY_SENTENCE = re.compile(
    r'^The 10 catalogued categories[^:]*:\s*(?P<categories>.+?)\.\s*$',
    re.MULTILINE,
)

def load_form(filename: str) -> dict:
    """Parse one issue form, failing loudly if it is missing or not a mapping."""
    form_path = ISSUE_TEMPLATE_DIR / filename
    assert form_path.is_file(), f"Missing issue form: {form_path.relative_to(REPO_ROOT)}"
    parsed = yaml.safe_load(form_path.read_text(encoding='utf-8'))
    assert isinstance(parsed, dict), f"{filename} must parse to a YAML mapping"
    return parsed

def find_element(form: dict, element_id: str) -> dict:
    """Return the body element with the given id."""
    for element in form.get('body', []):
        if element.get('id') == element_id:
            return element
    raise AssertionError(f"No body element with id '{element_id}'")

def count_required_fields(form: dict) -> int:
    """Count mandatory fields, including individually required checkbox options."""
    required = 0
    for element in form.get('body', []):
        if element.get('validations', {}).get('required') is True:
            required += 1
        for option in element.get('attributes', {}).get('options', []):
            if isinstance(option, dict) and option.get('required') is True:
                required += 1
    return required

def required_field_labels(form: dict) -> list:
    """Labels of the fields the form marks mandatory (checkbox options excluded)."""
    return [
        element['attributes']['label']
        for element in form.get('body', [])
        if element.get('validations', {}).get('required') is True
    ]

def canonical_categories() -> list:
    """The tech-debt taxonomy, read from its single source of truth: the form."""
    category_field = find_element(load_form('tech_debt.yml'), 'category')
    return list(category_field['attributes']['options'])

def skill_prose_categories() -> list:
    """The taxonomy as restated for agents in github-workflow/SKILL.md rule 4."""
    match = SKILL_CATEGORY_SENTENCE.search(GITHUB_WORKFLOW_SKILL.read_text(encoding='utf-8'))
    assert match, "github-workflow/SKILL.md must state 'The 10 catalogued categories...: <list>.'"
    return [category.strip() for category in match.group('categories').split(',')]

def tracked_files_containing(marker: str) -> set:
    """Repo-relative paths of tracked (or stageable) text files containing the marker."""
    try:
        # --others --exclude-standard includes new, not-yet-staged files, so a copy
        # of the taxonomy is caught before it is committed rather than after.
        listing = subprocess.run(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git ls-files unavailable; cannot enumerate tracked files")

    matches = set()
    for rel_path in listing:
        candidate = REPO_ROOT / rel_path
        if not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        if marker in content:
            matches.add(rel_path)
    return matches

def test_issue_forms_replace_legacy_markdown_templates():
    for filename in EXPECTED_FORMS:
        assert (ISSUE_TEMPLATE_DIR / filename).is_file(), f"Missing issue form {filename}"

    for legacy_name in LEGACY_MARKDOWN_TEMPLATES:
        legacy_path = ISSUE_TEMPLATE_DIR / legacy_name
        assert not legacy_path.exists(), (
            f"Legacy Markdown template {legacy_name} must be removed once the issue form lands"
        )

    stray_markdown = sorted(path.name for path in ISSUE_TEMPLATE_DIR.glob('*.md'))
    assert stray_markdown == [], f"ISSUE_TEMPLATE/ must hold forms only, found: {stray_markdown}"

def test_issue_chooser_config_is_preserved():
    """config.yml (blank issues off + contact links) must survive the conversion."""
    assert (ISSUE_TEMPLATE_DIR / 'config.yml').is_file(), (
        "config.yml is the issue chooser; converting templates must not delete it"
    )

@pytest.mark.parametrize('filename', sorted(EXPECTED_FORMS))
def test_forms_declare_valid_issue_form_schema(filename):
    form = load_form(filename)

    assert isinstance(form.get('name'), str) and form['name'].strip(), f"{filename}: needs a name"
    assert isinstance(form.get('description'), str) and form['description'].strip(), (
        f"{filename}: needs a description for the issue chooser"
    )

    body = form.get('body')
    assert isinstance(body, list) and body, f"{filename}: body must be a non-empty list"

    seen_ids = set()
    for index, element in enumerate(body):
        where = f"{filename}: body[{index}]"
        assert isinstance(element, dict), f"{where} must be a mapping"

        element_type = element.get('type')
        assert element_type in ALL_ELEMENT_TYPES, f"{where}: unknown type {element_type!r}"

        label = element.get('attributes', {}).get('label')
        if element_type == 'markdown':
            assert element.get('attributes', {}).get('value'), f"{where}: markdown needs a value"
            assert 'id' not in element, f"{where}: markdown blocks take no id"
            continue

        element_id = element.get('id')
        assert element_id, f"{where}: input elements need an id"
        assert element_id not in seen_ids, f"{where}: duplicate id {element_id!r}"
        seen_ids.add(element_id)
        assert label, f"{where}: input elements need a label"

@pytest.mark.parametrize('filename', sorted(EXPECTED_FORMS))
def test_forms_preserve_legacy_labels_and_title_prefixes(filename):
    form = load_form(filename)
    expected_labels, expected_title_prefix = EXPECTED_FORMS[filename]

    assert form.get('labels') == expected_labels, (
        f"{filename}: labels must stay {expected_labels} so existing triage queries keep matching"
    )
    assert form.get('title') == expected_title_prefix, (
        f"{filename}: title prefix must stay {expected_title_prefix!r}"
    )

@pytest.mark.parametrize('filename', sorted(EXPECTED_FORMS))
def test_required_field_set_stays_small(filename):
    required_count = count_required_fields(load_form(filename))

    assert required_count >= 1, f"{filename}: a form with no required field validates nothing"
    assert required_count <= MAX_REQUIRED_FIELDS_PER_FORM, (
        f"{filename}: {required_count} required fields exceeds the cap of "
        f"{MAX_REQUIRED_FIELDS_PER_FORM}; over-long forms get routed around, not filled in"
    )

def test_tech_debt_category_is_a_required_dropdown():
    category_field = find_element(load_form('tech_debt.yml'), 'category')

    assert category_field.get('type') == 'dropdown', (
        "tech_debt.yml: category must be a dropdown so the taxonomy is mechanically enforced"
    )
    assert category_field.get('validations', {}).get('required') is True, (
        "tech_debt.yml: the category dropdown must be required"
    )

    options = category_field.get('attributes', {}).get('options')
    assert isinstance(options, list), "tech_debt.yml: category options must be a list"
    assert len(options) == 10, f"tech_debt.yml: expected the 10 catalogued categories, got {len(options)}"
    assert len(set(options)) == len(options), "tech_debt.yml: category options must be unique"

def test_category_taxonomy_agrees_between_form_and_skill():
    """The prose in SKILL.md rule 4 must mirror the canonical dropdown exactly."""
    assert skill_prose_categories() == canonical_categories(), (
        "github-workflow/SKILL.md rule 4 and the tech_debt.yml category dropdown have drifted apart"
    )

def test_skill_names_the_form_as_the_canonical_taxonomy():
    assert TECH_DEBT_FORM_RELPATH in GITHUB_WORKFLOW_SKILL.read_text(encoding='utf-8'), (
        "github-workflow/SKILL.md must point at the form that owns the category list"
    )

def test_template_guide_defers_to_the_canonical_taxonomy():
    """Pattern 9 must reference the form instead of restating the 10 categories."""
    guide_text = TEMPLATE_GUIDE.read_text(encoding='utf-8')

    assert TECH_DEBT_FORM_RELPATH in guide_text, (
        "docs/TEMPLATE_GUIDE.md pattern 9 must reference the canonical category dropdown"
    )
    assert TAXONOMY_MARKER not in guide_text, (
        "docs/TEMPLATE_GUIDE.md must not restate the category list; link to the form instead"
    )

def test_no_third_hand_maintained_copy_of_the_taxonomy():
    copies = tracked_files_containing(TAXONOMY_MARKER) - {'tests/test_issue_templates.py'}

    assert copies == TAXONOMY_CANONICAL_FILES, (
        "The tech-debt taxonomy must live only in the form and its mirrored prose in "
        f"github-workflow/SKILL.md; found it in: {sorted(copies)}"
    )

def test_skill_prescribes_an_invocation_that_works_non_interactively():
    """`gh issue create --template` is rejected without a TTY; the skill must not prescribe it."""
    skill_text = GITHUB_WORKFLOW_SKILL.read_text(encoding='utf-8')

    # Only runnable examples are checked: the skill is expected to quote the rejected
    # invocation verbatim (in a non-bash transcript block) as evidence for the rule.
    runnable_examples = re.findall(r'^```bash\n(.*?)^```', skill_text, re.MULTILINE | re.DOTALL)
    non_interactive_template_use = [
        line for block in runnable_examples for line in block.splitlines()
        if 'gh issue create' in line and '--template' in line and '--web' not in line
    ]
    assert non_interactive_template_use == [], (
        "gh rejects `--template` alongside --body/--body-file and demands both without a TTY, "
        f"so it cannot be prescribed for agents: {non_interactive_template_use}"
    )

    for rejection_message in (
        '`--template` is not supported when using `--body` or `--body-file`',
        'must provide `--title` and `--body` when not running interactively',
    ):
        assert rejection_message in skill_text, (
            f"github-workflow/SKILL.md must cite gh's rejection ({rejection_message!r}) so the "
            "rule is not 'corrected' back to --template later"
        )

    assert '--body-file' in skill_text, (
        "github-workflow/SKILL.md must show agents how to file a structured body non-interactively"
    )
    assert 'gh issue create --web --template tech_debt.yml' in skill_text, (
        "github-workflow/SKILL.md must offer the browser path, where GitHub validates the form"
    )

def test_skill_example_body_mirrors_the_tech_debt_form_fields():
    """The documented agent body must carry every field the form marks required."""
    skill_text = GITHUB_WORKFLOW_SKILL.read_text(encoding='utf-8')

    for label in required_field_labels(load_form('tech_debt.yml')):
        assert f"### {label}" in skill_text, (
            f"github-workflow/SKILL.md's example body is missing the required '{label}' heading "
            "from tech_debt.yml"
        )
