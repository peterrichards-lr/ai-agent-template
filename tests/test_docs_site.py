"""
test_docs_site.py - Optional MkDocs Documentation Site Scaffold

Covers the opt-in documentation site shipped by the template: `mkdocs.yml`,
`.github/workflows/docs.yml`, `requirements-docs.txt`, the Diataxis skeleton
under `docs/`, and the `--docs-site` switch on `bootstrap_template.py`.

Two properties matter more than the file contents themselves:

1. **It is dormant until opted in.** A 200-line utility bootstrapped from this
   template must not acquire a Pages deployment it never asked for, so the
   workflow ships with its push trigger commented out and `--clean-template`
   deletes the whole scaffold unless `--docs-site` was passed.
2. **The Pages concurrency lesson survives.** `cancel-in-progress: false` here
   is a third case in this repository's convention, and the comment explaining
   why is the artefact worth protecting -- a future editor "harmonising" the
   workflows would otherwise delete a hard-won incident lesson.

Deliberately a dedicated module rather than an addition to
tests/test_template_scripts.py: the docs site is an optional, self-contained
subsystem spanning a config, a workflow, a requirements file and a doc tree.
pytest auto-discovers tests/test_*.py.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT_DIR / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

MKDOCS_CONFIG = ROOT_DIR / 'mkdocs.yml'
DOCS_WORKFLOW = ROOT_DIR / '.github' / 'workflows' / 'docs.yml'
DOCS_REQUIREMENTS = ROOT_DIR / 'requirements-docs.txt'
DEV_REQUIREMENTS = ROOT_DIR / 'requirements-dev.txt'
DOCS_DIR = ROOT_DIR / 'docs'
GITIGNORE = ROOT_DIR / '.gitignore'
DOCUMENTATION_SKILL = ROOT_DIR / '.agents' / 'skills' / 'documentation' / 'SKILL.md'
MAIN_RULESET = ROOT_DIR / '.github' / 'rulesets' / 'protect-main-branch.json'

# The four Diataxis divisions, as directory names under docs/.
DIATAXIS_DIVISIONS = ('tutorials', 'how-to', 'reference', 'explanation')

# The site home page is copied from README.md at build time rather than tracked,
# so the landing page is never maintained in two places.
GENERATED_HOME_PAGE = 'index.md'

FOOTER_REGEX = re.compile(
    r"([*_])Last Updated:\s*(\d{4}-\d{2}-\d{2})\1\s*\|\s*\1Last Reviewed:\s*(\d{4}-\d{2}-\d{2})\1"
)


def load_yaml_ignoring_unknown_tags(path: Path) -> dict:
    """Parse a YAML document, tolerating MkDocs' `!!python/name:` tags and YAML 1.1 `on:`."""

    class Tolerant(yaml.SafeLoader):
        pass

    Tolerant.add_multi_constructor(
        'tag:yaml.org,2002:python/name:', lambda loader, suffix, node: suffix)
    Tolerant.add_multi_constructor('!', lambda loader, suffix, node: suffix)

    data = yaml.load(path.read_text(encoding='utf-8'), Loader=Tolerant) or {}
    if True in data and 'on' not in data:
        data['on'] = data.pop(True)
    return data


def nav_targets(nav) -> list:
    """Flatten a MkDocs `nav:` tree into the list of page targets it references."""
    targets = []
    if isinstance(nav, str):
        targets.append(nav)
    elif isinstance(nav, list):
        for entry in nav:
            targets.extend(nav_targets(entry))
    elif isinstance(nav, dict):
        for value in nav.values():
            targets.extend(nav_targets(value))
    return targets


# ---------------------------------------------------------------------------
# mkdocs.yml
# ---------------------------------------------------------------------------

def test_mkdocs_config_uses_the_material_theme():
    """The two sibling projects both converged on mkdocs-material; the template ships it."""
    assert MKDOCS_CONFIG.exists(), "Expected mkdocs.yml at the repository root"

    config = load_yaml_ignoring_unknown_tags(MKDOCS_CONFIG)
    assert config.get('site_name'), "mkdocs.yml must declare a site_name"
    assert config.get('theme', {}).get('name') == 'material', (
        "mkdocs.yml must use the material theme")


def test_nav_declares_all_four_diataxis_divisions():
    """Tutorials / How-To / Reference / Explanation, in that order, plus the README home."""
    config = load_yaml_ignoring_unknown_tags(MKDOCS_CONFIG)
    nav = config.get('nav')
    assert nav, "mkdocs.yml must declare an explicit nav"

    section_titles = [key for entry in nav if isinstance(entry, dict) for key in entry]
    assert section_titles[0] == 'Home', (
        "The first nav entry must be Home, sourced from README.md at build time")

    targets = nav_targets(nav)
    for division in DIATAXIS_DIVISIONS:
        assert any(target.startswith(f'{division}/') for target in targets), (
            f"mkdocs.yml nav declares no page under docs/{division}/; the Diataxis "
            "skeleton must cover Tutorials, How-To, Reference and Explanation")


def test_every_navigated_page_exists_on_disk():
    """A nav entry pointing at a missing file publishes a 404 into the sidebar."""
    config = load_yaml_ignoring_unknown_tags(MKDOCS_CONFIG)
    targets = nav_targets(config.get('nav'))

    missing = [
        target for target in targets
        if not target.startswith(('http://', 'https://'))
        and target != GENERATED_HOME_PAGE
        and not (DOCS_DIR / target).exists()
    ]
    assert not missing, f"mkdocs.yml nav references files that do not exist: {missing}"


def test_the_diataxis_skeleton_directories_are_shipped_with_an_index():
    """An empty division is invisible; each ships an index explaining what belongs in it."""
    for division in DIATAXIS_DIVISIONS:
        index = DOCS_DIR / division / 'index.md'
        assert index.exists(), f"Expected docs/{division}/index.md to ship with the skeleton"
        assert FOOTER_REGEX.search(index.read_text(encoding='utf-8')), (
            f"docs/{division}/index.md is missing the timestamp footer every .md must carry")


def test_the_site_home_page_is_not_maintained_twice():
    """README.md is the home page; a tracked copy under docs/ would silently drift."""
    assert not (DOCS_DIR / GENERATED_HOME_PAGE).exists() or \
        f'docs/{GENERATED_HOME_PAGE}' in GITIGNORE.read_text(encoding='utf-8'), (
        "docs/index.md must be generated from README.md, not tracked as a second copy")

    gitignore = GITIGNORE.read_text(encoding='utf-8')
    assert f'docs/{GENERATED_HOME_PAGE}' in gitignore, (
        "Expected .gitignore to cover the generated docs/index.md home page")
    assert 'site/' in gitignore, (
        "Expected .gitignore to cover the MkDocs build output directory")


# ---------------------------------------------------------------------------
# .github/workflows/docs.yml
# ---------------------------------------------------------------------------

def test_docs_workflow_ships_dormant_with_no_automatic_trigger():
    """Opt-in means the template's own copy never fires on a push."""
    assert DOCS_WORKFLOW.exists(), "Expected .github/workflows/docs.yml"

    workflow = load_yaml_ignoring_unknown_tags(DOCS_WORKFLOW)
    triggers = set(workflow.get('on', {}))
    assert triggers == {'workflow_dispatch'}, (
        "docs.yml must ship with workflow_dispatch as its only live trigger so a "
        f"repository that did not opt in never deploys Pages; found {sorted(triggers)}")


def test_docs_workflow_carries_a_commented_push_trigger_for_bootstrap_to_enable():
    """`--docs-site` uncomments this block, so the markers and body must be present."""
    text = DOCS_WORKFLOW.read_text(encoding='utf-8')

    assert 'OPT-IN PUSH TRIGGER' in text, (
        "docs.yml must delimit the commented push trigger that --docs-site uncomments")
    assert re.search(r'^\s*#\s*push:\s*$', text, re.MULTILINE), (
        "docs.yml must ship the push trigger commented out")


def test_pages_deploy_never_cancels_an_in_flight_deployment():
    """A half-applied Pages deploy leaves the published site broken. See the LDM incident."""
    workflow = load_yaml_ignoring_unknown_tags(DOCS_WORKFLOW)
    concurrency = workflow.get('concurrency')
    assert isinstance(concurrency, dict), "docs.yml must declare a concurrency block"

    # Evaluated for both events: the expressions are the contract, so read them as GitHub
    # would. A push (or a manual run) deploys; a pull request only builds and checks.
    group, cancel = concurrency.get('group'), concurrency.get('cancel-in-progress')
    assert group == ("${{ github.event_name == 'pull_request' && "
                     "format('docs-pr-{0}', github.event.pull_request.number) || 'pages' }}"), (
        "a deploy must share the single 'pages' group, and a PR run must not join it")
    assert cancel == "${{ github.event_name == 'pull_request' }}", (
        "cancel-in-progress must be false for a deploy: cancelling an in-flight Pages "
        "deployment leaves the live site in a half-applied state")


def test_the_pages_concurrency_comment_explains_the_third_case():
    """The reasoning is the artefact; without it a future editor 'harmonises' it away."""
    text = DOCS_WORKFLOW.read_text(encoding='utf-8')
    comment_block = text.split('concurrency:')[0]

    assert 'security-scan.yml' in comment_block, (
        "The concurrency comment must contrast with security-scan.yml, which sets "
        "cancel-in-progress: true because nothing gates on it")
    assert 'required status check' in comment_block, (
        "The concurrency comment must explain that, unlike ci.yml, this workflow is "
        "NOT a required status check -- so it is a third case, not the same rule")
    assert 'half-applied' in comment_block, (
        "The concurrency comment must state the failure mode: a half-applied deploy "
        "leaves the live site broken")


def test_docs_workflow_installs_only_the_documentation_requirements():
    """mkdocs must not leak into the language-agnostic quality gate every adopter installs."""
    # Comments are allowed to mention requirements-dev.txt (the whole point is
    # explaining why it is not used here); executed lines are not.
    executed = '\n'.join(
        line for line in DOCS_WORKFLOW.read_text(encoding='utf-8').splitlines()
        if not line.lstrip().startswith('#'))

    assert 'requirements-docs.txt' in executed, (
        "docs.yml must install requirements-docs.txt")
    assert 'requirements-dev.txt' not in executed, (
        "docs.yml must not install requirements-dev.txt; the docs site owns its own "
        "dependency file so non-docs adopters never pay for mkdocs-material")


def test_docs_workflow_seeds_the_home_page_from_the_readme():
    """The single-source home page only works if the build actually copies it in."""
    text = DOCS_WORKFLOW.read_text(encoding='utf-8')
    assert re.search(r'cp\s+README\.md\s+docs/index\.md', text), (
        "docs.yml must copy README.md to docs/index.md before building, so the site "
        "home and the GitHub landing page are the same document")


def test_docs_workflow_is_not_a_required_status_check():
    """A Pages deploy gating every merge would block the repository on a Pages outage."""
    ruleset = json.loads(MAIN_RULESET.read_text(encoding='utf-8'))
    required_contexts = {
        check.get('context')
        for rule in ruleset.get('rules', [])
        for check in rule.get('parameters', {}).get('required_status_checks', [])
    }

    workflow = load_yaml_ignoring_unknown_tags(DOCS_WORKFLOW)
    docs_job_names = {
        job.get('name') for job in workflow.get('jobs', {}).values() if job.get('name')
    }
    assert docs_job_names, "Expected the docs workflow to name its jobs"

    overlap = docs_job_names & required_contexts
    assert not overlap, (
        "The docs deployment must not be a required status check in "
        f"protect-main-branch.json; found {sorted(overlap)}")


# ---------------------------------------------------------------------------
# Dependency placement
# ---------------------------------------------------------------------------

def test_mkdocs_dependencies_live_outside_the_language_agnostic_requirements():
    """requirements-dev.txt is installed by every adopter; mkdocs is not universal."""
    dev = DEV_REQUIREMENTS.read_text(encoding='utf-8').lower()
    assert 'mkdocs' not in dev, (
        "mkdocs dependencies must not be added to requirements-dev.txt, which every "
        "bootstrapped project installs regardless of whether it has a docs site")


def test_documentation_requirements_pin_mkdocs_and_material():
    """Pinned, like every other requirements file in this repository."""
    assert DOCS_REQUIREMENTS.exists(), "Expected requirements-docs.txt"
    text = DOCS_REQUIREMENTS.read_text(encoding='utf-8')

    for package in ('mkdocs==', 'mkdocs-material=='):
        assert package in text, f"requirements-docs.txt must pin {package.rstrip('=')}"


# ---------------------------------------------------------------------------
# bootstrap_template.py --docs-site
# ---------------------------------------------------------------------------

def test_bootstrap_exposes_a_docs_site_flag():
    from bootstrap_template import build_arg_parser

    args = build_arg_parser().parse_args([
        '--name', 'demo', '--repo-owner', 'acme', '--conduct-email', 'c@example.com',
        '--docs-site',
    ])
    assert args.docs_site is True, "bootstrap_template.py must accept --docs-site"

    defaults = build_arg_parser().parse_args([
        '--name', 'demo', '--repo-owner', 'acme', '--conduct-email', 'c@example.com',
    ])
    assert defaults.docs_site is False, "The docs site must be opt-in, not the default"


def _seed_docs_scaffold(tmp_path: Path) -> Path:
    """Copy the shipped docs-site scaffold into an isolated tree."""
    (tmp_path / '.github' / 'workflows').mkdir(parents=True)
    (tmp_path / 'docs').mkdir(parents=True)
    (tmp_path / '.github' / 'workflows' / 'docs.yml').write_text(
        DOCS_WORKFLOW.read_text(encoding='utf-8'), encoding='utf-8')
    (tmp_path / 'mkdocs.yml').write_text(
        MKDOCS_CONFIG.read_text(encoding='utf-8'), encoding='utf-8')
    (tmp_path / 'requirements-docs.txt').write_text(
        DOCS_REQUIREMENTS.read_text(encoding='utf-8'), encoding='utf-8')
    (tmp_path / 'docs' / 'how-to').mkdir(parents=True)
    (tmp_path / 'docs' / 'how-to' / 'publish-the-documentation-site.md').write_text(
        '# Publish\n', encoding='utf-8')
    return tmp_path


def test_docs_site_flag_activates_the_push_trigger(tmp_path):
    from bootstrap_template import enable_docs_site

    project = _seed_docs_scaffold(tmp_path)
    assert enable_docs_site(project, project_name='demo', repo_owner='acme') is True

    workflow = load_yaml_ignoring_unknown_tags(project / '.github' / 'workflows' / 'docs.yml')
    triggers = workflow.get('on', {})
    assert 'push' in triggers, (
        "--docs-site must uncomment the push trigger so the site deploys on merge")
    assert 'mkdocs.yml' in triggers['push']['paths'], (
        "The activated push trigger must still carry its path filter")

    config = load_yaml_ignoring_unknown_tags(project / 'mkdocs.yml')
    assert config['site_name'] == 'demo', "--docs-site must seed site_name from --name"
    assert config['repo_url'] == 'https://github.com/acme/demo', (
        "--docs-site must seed repo_url from --repo-owner and --name")
    assert config['site_url'] == 'https://acme.github.io/demo/', (
        "--docs-site must seed the GitHub Pages site_url")


def test_cleanup_removes_the_whole_scaffold_when_the_site_was_not_requested(tmp_path):
    from bootstrap_template import clean_docs_site_scaffold

    project = _seed_docs_scaffold(tmp_path)
    removed = clean_docs_site_scaffold(project, docs_site=False)

    assert removed == [
        '.github/workflows/docs.yml', 'mkdocs.yml', 'requirements-docs.txt',
    ], f"Expected the docs-site scaffold to be removed wholesale; removed {removed}"
    assert not (project / 'mkdocs.yml').exists()
    assert not (project / '.github' / 'workflows' / 'docs.yml').exists()
    assert not (project / 'requirements-docs.txt').exists()

    # The how-to guide survives on purpose: the decision is reversible, and the
    # guide is what tells the adopter how to reverse it. Removing it would also
    # leave a dead link in docs/how-to/index.md, which is not removed.
    assert (project / 'docs' / 'how-to' / 'publish-the-documentation-site.md').exists()


def test_cleanup_keeps_the_scaffold_when_the_site_was_requested(tmp_path):
    from bootstrap_template import clean_docs_site_scaffold

    project = _seed_docs_scaffold(tmp_path)
    assert clean_docs_site_scaffold(project, docs_site=True) == []
    assert (project / 'mkdocs.yml').exists()


def test_the_diataxis_skeleton_survives_cleanup(tmp_path):
    """Diataxis organisation is worth keeping even for a repo with no published site."""
    from bootstrap_template import clean_docs_site_scaffold

    project = _seed_docs_scaffold(tmp_path)
    for division in DIATAXIS_DIVISIONS:
        (project / 'docs' / division).mkdir(parents=True, exist_ok=True)
        (project / 'docs' / division / 'index.md').write_text('# x\n', encoding='utf-8')

    clean_docs_site_scaffold(project, docs_site=False)

    for division in DIATAXIS_DIVISIONS:
        assert (project / 'docs' / division / 'index.md').exists(), (
            f"docs/{division}/ must survive: the Diataxis structure is useful with or "
            "without a rendered site")


# ---------------------------------------------------------------------------
# Timestamp tooling over the nested docs/ tree
# ---------------------------------------------------------------------------

def test_timestamp_tooling_traverses_nested_docs_subdirectories(tmp_path):
    """The Diataxis tree is two levels deep; footer injection must reach into it."""
    from append_timestamps import append_timestamps
    from check_docs_review import check_docs

    nested = tmp_path / 'docs' / 'how-to' / 'deployment'
    nested.mkdir(parents=True)
    page = nested / 'publish.md'
    page.write_text('# Publish\n\nBody.\n', encoding='utf-8')

    append_timestamps(tmp_path)

    assert FOOTER_REGEX.search(page.read_text(encoding='utf-8')), (
        "append_timestamps.py must inject a footer into docs/<division>/<topic>/*.md")
    assert check_docs(180, 180, 180, root_dir=tmp_path) is True


def test_generated_site_output_is_never_scanned_for_footers(tmp_path):
    """`mkdocs build` copies .md files into the output dir; they are not documentation."""
    from check_docs_review import IGNORE_DIRS, check_docs

    assert 'site' in IGNORE_DIRS and '_site' in IGNORE_DIRS, (
        "The MkDocs output directories must be ignored by the documentation scanners, "
        "or a local build turns every generated page into a review-policy violation")

    for output_dir in ('site', '_site'):
        generated = tmp_path / output_dir
        generated.mkdir()
        (generated / 'index.md').write_text('# Generated\n', encoding='utf-8')

    assert check_docs(180, 180, 180, root_dir=tmp_path) is True


# ---------------------------------------------------------------------------
# Agent guidance
# ---------------------------------------------------------------------------

def test_documentation_skill_says_where_a_new_document_belongs():
    """Diataxis placement is the decision agents get wrong without explicit guidance."""
    skill = DOCUMENTATION_SKILL.read_text(encoding='utf-8')

    assert 'Diátaxis' in skill or 'Diataxis' in skill, (
        ".agents/skills/documentation/SKILL.md must name the Diataxis model")
    for division in ('docs/tutorials/', 'docs/how-to/', 'docs/reference/', 'docs/explanation/'):
        assert division in skill, (
            f"The documentation skill must tell an agent when a doc belongs in {division}")


def test_the_docs_site_is_documented_as_optional():
    """An adopter must be able to find the flag that turns this on."""
    guide = (ROOT_DIR / 'docs' / 'TEMPLATE_GUIDE.md').read_text(encoding='utf-8')
    assert '--docs-site' in guide, (
        "docs/TEMPLATE_GUIDE.md must document the --docs-site opt-in flag")


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    subprocess.run([sys.executable, '-c', 'import mkdocs'], capture_output=True).returncode != 0,
    reason="mkdocs is not installed; requirements-docs.txt is deliberately not part of "
           "the language-agnostic quality gate",
)
def test_the_shipped_configuration_builds(tmp_path):
    """Belt and braces for the environments that do have mkdocs available."""
    (DOCS_DIR / GENERATED_HOME_PAGE).write_text(
        (ROOT_DIR / 'README.md').read_text(encoding='utf-8'), encoding='utf-8')
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'mkdocs', 'build', '--site-dir', str(tmp_path / '_site')],
            cwd=ROOT_DIR, capture_output=True, text=True, check=False)
    finally:
        (DOCS_DIR / GENERATED_HOME_PAGE).unlink(missing_ok=True)

    assert result.returncode == 0, f"mkdocs build failed:\n{result.stderr}"


# ---------------------------------------------------------------------------
# The shared docs files and the docs-site standard (#135)
# ---------------------------------------------------------------------------

SHARED_DOCS_FILES = (
    'scripts/mkdocs_github_alerts.py',
    'scripts/check_docs_rendered.py',
    'overrides/main.html',
    'overrides/partials/copyright.html',
    '.agents/templates/docs-profiles/liferay/liferay-blue.css',
)
LIFERAY_PROFILE = ROOT_DIR / '.agents' / 'templates' / 'docs-profiles' / 'liferay'
STANDARD_SKILL = ROOT_DIR / '.agents' / 'skills' / 'docs-site-standard' / 'SKILL.md'

needs_mkdocs = pytest.mark.skipif(
    subprocess.run([sys.executable, '-c', 'import mkdocs, material'],
                   capture_output=True).returncode != 0,
    reason="mkdocs-material is not installed; requirements-docs.txt is deliberately not part "
           "of the language-agnostic quality gate")


@pytest.mark.parametrize('rel_path', SHARED_DOCS_FILES)
def test_every_shared_docs_file_names_the_template_as_canonical(rel_path):
    """The header is where a downstream editor looks first; it must send them upstream."""
    text = (ROOT_DIR / rel_path).read_text(encoding='utf-8')
    header = text[:1500]
    assert 'SHARED FILE' in header
    assert 'peterrichards-lr/ai-agent-template' in header, (
        f"{rel_path} must name ai-agent-template as the canonical repository")
    assert 'Never edit a copy' in header
    assert 'peterrichards-lr/lfr-tunnel' not in header, (
        f"{rel_path} still names lfr-tunnel as canonical")


def test_contributing_states_the_shared_docs_files_rule():
    contributing = (ROOT_DIR / 'CONTRIBUTING.md').read_text(encoding='utf-8')
    section = contributing.split('### Shared docs files', 1)
    assert len(section) == 2, "CONTRIBUTING.md must have a 'Shared docs files' section"
    for rel_path in SHARED_DOCS_FILES:
        name = rel_path.split('/')[-1]
        assert name in section[1], f"CONTRIBUTING.md's shared-files list is missing {name}"
    assert 'Never edit a downstream copy' in section[1]


def test_the_standard_skill_records_the_measured_case_against_relaxing_the_lift():
    skill = STANDARD_SKILL.read_text(encoding='utf-8')
    assert 'the strict rule lifts 1;' in skill and 'bold-lead-only rule lifts 29' in skill
    for check in ('LEAKED-ALERT', 'STYLE-TITLE', 'UNDATED-PAGE', 'ABOUT-LINK', 'NAV',
                  'MISSING-VERIFICATION', 'MISSING-SOCIAL', 'NO-NOTICE', 'HOME-LAYOUT'):
        assert check in skill, f"the skill must document the {check} check"
    assert 'DESIGN-10350' in skill, "the Liferay branding rule must cite its source"


def test_the_nav_seed_follows_the_standard_order():
    from check_docs_rendered import STANDARD_NAV

    nav = load_yaml_ignoring_unknown_tags(MKDOCS_CONFIG)['nav']
    labels = [key for entry in nav for key in entry]
    assert all(label in STANDARD_NAV for label in labels), labels
    assert labels == sorted(labels, key=STANDARD_NAV.index), labels
    assert labels[-1] == 'About these docs'


# --- The alerts hook --------------------------------------------------------

def _hook():
    import mkdocs_github_alerts
    return mkdocs_github_alerts._convert


@pytest.mark.parametrize('marker, style, label', [
    ('NOTE', 'note', 'Note'),
    ('TIP', 'tip', 'Tip'),
    ('IMPORTANT', 'info', 'Important'),
    ('WARNING', 'warning', 'Warning'),
    ('CAUTION', 'danger', 'Caution'),
])
def test_alerts_keep_githubs_label_and_borrow_only_the_style(marker, style, label):
    out = _hook()(f"> [!{marker}]\n> Body text.\n")
    assert out.splitlines()[0] == f'!!! {style} "{label}"'
    assert '    Body text.' in out


def test_the_strict_title_lift_renders_info_with_the_lifted_title():
    out = _hook()("> [!NOTE]\n> ℹ️ **Community project** — not an official product.\n")
    assert out.splitlines()[0] == '!!! info "Community project"'
    assert '    Not an official product.' in out, "the remainder starts a sentence"


def test_a_bare_information_sign_without_its_variation_selector_still_lifts():
    out = _hook()("> [!NOTE]\n> ℹ **Community project** — text.\n")
    assert out.splitlines()[0] == '!!! info "Community project"'


@pytest.mark.parametrize('first_line', [
    '**The bundle does not carry a key** — so it cannot start.',   # bold lead, no emoji
    'Note **bold** — not an emoji lead.',                           # a word, not an emoji
    'ℹ️ **Bold** but no dash after it.',                            # no em dash
])
def test_anything_short_of_emoji_bold_dash_is_not_lifted(first_line):
    out = _hook()(f"> [!WARNING]\n> {first_line}\n")
    assert out.splitlines()[0] == '!!! warning "Warning"'


def test_a_lifted_remainder_keeps_the_case_of_a_name():
    out = _hook()("> [!TIP]\n> 💡 **Tip title** — macOS needs this.\n")
    assert '    macOS needs this.' in out


def test_markers_inside_fenced_code_are_left_alone():
    source = "```markdown\n> [!NOTE]\n> example\n```\n"
    assert _hook()(source) == source


# --- The rendered-output check, on a synthetic site -------------------------

RELATED_ROWS = [
    ('Liferay Docker Manager', 'https://peterrichards-lr.github.io/liferay-docker-manager/',
     'Run, manage and develop Liferay DXP and Portal environments in Docker.'),
    ('Liferay AI Commerce Accelerator',
     'https://peterrichards-lr.github.io/liferay-ai-commerce-accelerator/',
     'Generate and manage AI-driven commerce data in Liferay DXP.'),
    ('Liferay Tunnel', 'https://peterrichards-lr.github.io/lfr-tunnel/',
     'Securely expose a local Liferay environment on a public HTTPS subdomain.'),
]
RELATED_INTRO = ('Three community tools from the same maintainer. None is an official Liferay '
                 'product or covered by Liferay Support.')
FOOTER_HTML = '<p><em>Last Updated: 2026-10-15</em> | <em>Last Reviewed: 2026-10-15</em></p>'


def turn_on_profile_checks(text: str) -> str:
    """What an adopter does once the home page is written: switch on the notice and layout,
    and delete their two waives, so the profile requires them (#155)."""
    out = text.replace('home_layout: false', 'home_layout: true', 1)
    for name in ('NO-NOTICE', 'HOME-LAYOUT'):
        out, removed = re.subn(r'\n +' + name + r': [^\n]*', '', out, count=1)
        assert removed == 1, f"the profile ships no {name} waive to delete"
    out = out.replace('# notice:', 'notice:', 1)
    for key in ('title:', 'text:', 'link_text:'):
        out = re.sub(r'#   (' + key + ')', r'  \1', out, count=1)
    assert out.count('home_layout: true') == 1 and '# notice:' not in out
    assert not re.search(r'#   (title|text|link_text):', out)
    return out


def _liferay_config():
    """The Liferay profile's own site.yml, set up as an adopter whose home page is written."""
    site = yaml.safe_load(turn_on_profile_checks(
        (LIFERAY_PROFILE / 'site.yml').read_text(encoding='utf-8')
        .replace('<PROJECT_NAME_PLACEHOLDER>', 'Liferay Tunnel')))
    return {'site_name': 'lfr-tunnel', **site}


def _nav(labels):
    items = ''.join(f'<li class="md-nav__item"><a href="#" class="md-nav__link">'
                    f'<span class="md-ellipsis">{label}</span></a>'
                    f'<nav class="md-nav"><ul class="md-nav__list"><li class="md-nav__item">'
                    f'<a class="md-nav__link"><span class="md-ellipsis">Nested page</span></a>'
                    f'<nav class="md-nav md-nav--secondary"><ul class="md-nav__list"><li>'
                    f'<a class="md-nav__link"><span class="md-ellipsis">A Title Case Heading'
                    f'</span></a></li></ul></nav>'
                    f'</li></ul></nav></li>' for label in labels)
    return (f'<nav class="md-nav md-nav--primary" data-md-level="0">'
            f'<ul class="md-nav__list">{items}</ul></nav>')


def _page(article, about_href, nav=('Home', 'Tutorials', 'How-to guides', 'About these docs'),
          footer=FOOTER_HTML):
    return (f'<html><head></head><body>{_nav(nav)}<article class="md-content__inner">'
            f'{article}<hr>{footer}</article><footer><div class="md-copyright">'
            f'<div class="md-copyright__highlight">A project · '
            f'<a href="{about_href}">About these docs</a></div></div></footer></body></html>')


GOOD_HOME = (
    '<h1 id="liferay-tunnel-documentation">Liferay Tunnel documentation</h1>'
    '<p>What it does.</p>'
    '<div class="admonition info"><p class="admonition-title">Community project</p>'
    '<p>Not an official Liferay product and not covered by Liferay Support. '
    '<a href="about/">About this project</a></p></div>'
    '<h2 id="i-want-to">I want to…</h2>'
    '<table><thead><tr><th>I want to…</th><th>Go to</th></tr></thead><tbody>'
    '<tr><td>Share my local site</td><td><a href="x/">X</a></td></tr></tbody></table>'
    '<h2 id="by-subject">By subject</h2><h3 id="client-guides">Client guides</h3><p>…</p>'
    '<h2 id="related-liferay-tools">Related Liferay tools</h2>'
    f'<p>{RELATED_INTRO}</p>'
    '<table><thead><tr><th>Tool</th><th>What it does</th></tr></thead><tbody>'
    + ''.join(f'<tr><td>{name}</td><td>You are here. {desc}</td></tr>' if name == 'Liferay Tunnel'
              else f'<tr><td><a href="{url}">{name}</a></td><td>{desc}</td></tr>'
              for name, url, desc in RELATED_ROWS)
    + '</tbody></table>'
)


def _write_site(root: Path, home=GOOD_HOME, nav=None, page_body='<h1>Guide</h1><p>Text.</p>',
                nested_about='../../about/', nested_footer=FOOTER_HTML, nested=None):
    kwargs = {'nav': nav} if nav else {}
    pages = {
        'index.html': _page(home, 'about/', **kwargs),
        'about/index.html': _page('<h1>About these docs</h1>', './', **kwargs),
        'guides/index.html': _page('<h1>Guides</h1>', '../about/', **kwargs),  # MIN_PAGES (#141)
        'guides/setup/index.html': _page(page_body, nested_about, footer=nested_footer, **kwargs),
        '404.html': '<html><body>Not found</body></html>',
    }
    if nested:
        pages = {rel: html.replace('>Nested page<', f'>{nested}<') for rel, html in pages.items()}
    for rel, html in pages.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(html, encoding='utf-8')
    return root


def _run_check(site: Path, config: dict, capsys):
    from check_docs_rendered import run
    code = run(site, config)
    return code, capsys.readouterr().out


def test_rendered_check_passes_a_conforming_site(tmp_path, capsys):
    code, out = _run_check(_write_site(tmp_path), _liferay_config(), capsys)
    assert code == 0, out
    assert 'HOME-LAYOUT' in out and 'NO-NOTICE' in out


@pytest.mark.parametrize('label, mutate, expected', [
    ('a leaked alert marker', {'page_body': '<blockquote><p>[!WARNING] x</p></blockquote>'},
     'LEAKED-ALERT'),
    ('a mermaid block rendered as code', {'page_body': '<pre class="language-mermaid">a</pre>'},
     'UNRENDERED-DIAGRAM'),
    ('an alert titled with the style name',
     {'page_body': '<div class="admonition info">\n  <p class="admonition-title">Info</p></div>'},
     'STYLE-TITLE'),
    ('a footer About link that 404s on a nested page', {'nested_about': 'about/'}, 'ABOUT-LINK'),
    ('a page without its review footer', {'nested_footer': ''}, 'UNDATED-PAGE'),
    ('a review footer only inside a code block',
     {'nested_footer': '<pre><code>*Last Updated: 2026-10-15* | *Last Reviewed: 2026-10-15*'
                       '</code></pre>'}, 'UNDATED-PAGE'),
    ('an I-want-to column headed "Read"',
     {'home': GOOD_HOME.replace('<th>Go to</th>', '<th>Read</th>')}, 'directly under #i-want-to'),
    ('a paragraph between #i-want-to and its table',
     {'home': GOOD_HOME.replace('I want to…</h2>', 'I want to…</h2><p>Pick one.</p>')},
     'directly under #i-want-to'),
    ('a second "Related" heading',
     {'home': GOOD_HOME.replace('<h3 id="client-guides">',
                                '<h3 id="related-reading">Related reading</h3>'
                                '<h3 id="client-guides">')}, 'headings with the word "Related"'),
    ('a related table headed "Description"',
     {'home': GOOD_HOME.replace('<th>What it does</th>', '<th>Description</th>')},
     'after the related intro'),
    ('a title-case nav label', {'nav': ('Home', 'How-To Guides', 'About these docs')}, 'NAV'),
    ('a nav label outside the standard', {'nav': ('Home', 'Client Guides', 'About these docs')},
     'NAV'),
    ('a title-case label below the top level',
     {'nav': ('Home', 'How-to guides', 'About these docs'), 'nested': 'Getting Started Fast'},
     'title case'),
    ('nav sections out of order', {'nav': ('Home', 'Reference', 'Tutorials', 'About these docs')},
     'NAV'),
    ('About these docs not last', {'nav': ('Home', 'About these docs', 'Reference')}, 'NAV'),
    ('the notice titled "Info"',
     {'home': GOOD_HOME.replace('>Community project<', '>Info<')}, 'NO-NOTICE'),
    ('the notice as a note callout',
     {'home': GOOD_HOME.replace('admonition info', 'admonition note')}, 'NO-NOTICE'),
    ('the notice without its link',
     {'home': GOOD_HOME.replace('<a href="about/">About this project</a>', '')}, 'NO-NOTICE'),
    ('an H1 in title case',
     {'home': GOOD_HOME.replace('Tunnel documentation<', 'Tunnel Documentation<')}, 'H1 is'),
    ('"I want to..." with three dots',
     {'home': GOOD_HOME.replace('I want to…</h2>', 'I want to...</h2>')}, 'H2s'),
    ('a section after the related one',
     {'home': GOOD_HOME + '<h2 id="showcase">Showcase</h2>'}, 'H2s'),
    ('a task row ending in a full stop',
     {'home': GOOD_HOME.replace('Share my local site<', 'Share my local site.<')}, 'task rows'),
    ('a numbered subsection',
     {'home': GOOD_HOME.replace('>Client guides<', '>1. Client guides<')}, 'subsections'),
    ('a reworded related intro',
     {'home': GOOD_HOME.replace('None is an official', 'Neither is an official')},
     'shared intro'),
    ('a related description reworded',
     {'home': GOOD_HOME.replace('Run, manage and develop', 'Run and develop')}, 'related rows'),
    ('"You are here." at the end of the row',
     {'home': GOOD_HOME.replace(
         'You are here. Securely expose a local Liferay environment on a public HTTPS subdomain.',
         'Securely expose a local Liferay environment on a public HTTPS subdomain. You are here.')},
     'related rows'),
    ('an emoji in a heading',
     {'home': GOOD_HOME.replace('>Client guides<', '>📖 Client guides<')}, 'emoji'),
])
def test_rendered_check_fails_each_broken_rule(tmp_path, capsys, label, mutate, expected):
    code, out = _run_check(_write_site(tmp_path, **mutate), _liferay_config(), capsys)
    assert code == 1, f"{label}: the check passed\n{out}"
    assert expected in out, f"{label}: expected {expected!r} in\n{out}"


def test_a_trademark_sign_and_the_word_unrelated_are_not_failures(tmp_path, capsys):
    """Narrowness controls: © ® ™ are typography, and 'Unrelated' is not a second Related."""
    home = GOOD_HOME.replace('>Client guides<', '>Liferay™ guides<').replace(
        '<p>…</p>', '<h3 id="unrelated">Unrelated notes</h3>')
    code, out = _run_check(_write_site(tmp_path, home=home), _liferay_config(), capsys)
    assert code == 0, out


def test_rendered_check_skips_unconfigured_checks(tmp_path, capsys):
    """A generic site configures no notice and no layout: neither is asserted."""
    site = _write_site(tmp_path, home='<h1>demo</h1><p>Hello.</p>')
    code, out = _run_check(site, {'site_name': 'demo'}, capsys)
    assert code == 0, out
    assert 'HOME-LAYOUT' not in out and 'NO-NOTICE' not in out


def test_rendered_check_requires_configured_verification_and_social_tags(tmp_path, capsys):
    site = _write_site(tmp_path)
    config = {'site_name': 'demo', 'site_url': 'https://acme.github.io/demo/',
              'extra': {'google_site_verification': 'TOKEN',
                        'social_image': 'assets/social.png'}}
    code, out = _run_check(site, config, capsys)
    assert code == 1
    assert 'MISSING-VERIFICATION' in out and 'MISSING-SOCIAL' in out


def test_rendered_check_refuses_to_pass_a_near_empty_build(tmp_path, capsys):
    (tmp_path / 'index.html').write_text('<html></html>', encoding='utf-8')
    code, out = _run_check(tmp_path, {}, capsys)
    assert code == 1 and 'NO-SCAN' in out


# --- Bootstrap: --docs-profile ------------------------------------------------

def _seed_profile_project(tmp_path: Path) -> Path:
    project = _seed_docs_scaffold(tmp_path)
    profile = project / '.agents' / 'templates' / 'docs-profiles' / 'liferay'
    profile.mkdir(parents=True)
    for source in LIFERAY_PROFILE.iterdir():
        (profile / source.name).write_bytes(source.read_bytes())
    seed = project / '.agents' / 'templates' / 'template-ref.md'
    seed.write_text((ROOT_DIR / '.agents' / 'templates' / 'template-ref.md')
                    .read_text(encoding='utf-8'), encoding='utf-8')
    (project / '.agents' / 'TEMPLATE_REF.md').write_text(
        seed.read_text(encoding='utf-8'), encoding='utf-8')
    return project


def test_docs_profile_requires_docs_site():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / 'bootstrap_template.py'), '--name', 'demo',
         '--repo-owner', 'acme', '--conduct-email', 'c@example.com',
         '--docs-profile', 'liferay', '--dry-run'],
        capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert '--docs-profile requires --docs-site' in result.stderr


def test_every_shipped_profile_is_a_choice_and_complete():
    from bootstrap_template import DOCS_PROFILE_BLOCKS, DOCS_PROFILES

    on_disk = sorted(d.name for d in (ROOT_DIR / '.agents' / 'templates' / 'docs-profiles')
                     .iterdir() if d.is_dir())
    assert on_disk == sorted(DOCS_PROFILES)
    for profile in DOCS_PROFILES:
        for block in DOCS_PROFILE_BLOCKS:
            assert (ROOT_DIR / '.agents' / 'templates' / 'docs-profiles' / profile
                    / f'{block}.yml').exists()


def test_liferay_profile_replaces_the_blocks_copies_the_stylesheet_and_maps_it(tmp_path):
    from bootstrap_template import apply_docs_profile, enable_docs_site, record_path_mappings
    from check_template_drift import parse_path_mappings

    project = _seed_profile_project(tmp_path)
    enable_docs_site(project, project_name='lfr-tunnel', repo_owner='acme')
    mappings = apply_docs_profile(project, 'liferay', 'lfr-tunnel', repo_owner='acme')

    config = load_yaml_ignoring_unknown_tags(project / 'mkdocs.yml')
    assert {scheme['primary'] for scheme in config['theme']['palette']} == {'custom'}
    assert config['extra_css'] == ['assets/stylesheets/liferay-blue.css']
    standard = config['extra']['docs_standard']
    # Off until the home page is written: a fresh project's first deploy must not fail on it.
    assert standard['home_layout'] is False and 'notice' not in standard
    assert standard['project_name'] == 'lfr-tunnel'
    assert yaml.safe_load(turn_on_profile_checks(
        (project / 'mkdocs.yml').read_text(encoding='utf-8').split('# >>> DOCS PROFILE: site')[1]
        .split('\n', 1)[1].split('# <<< DOCS PROFILE: site')[0]))['extra']['docs_standard'][
            'notice']['title'] == 'Community project'
    assert [row['name'] for row in standard['related']['rows']] == [
        name for name, _, _ in RELATED_ROWS]
    assert 'A community project' in config['copyright']

    css = project / 'docs' / 'assets' / 'stylesheets' / 'liferay-blue.css'
    assert css.read_bytes() == (LIFERAY_PROFILE / 'liferay-blue.css').read_bytes(), (
        "the stylesheet must be copied byte for byte: the drift check compares bytes")
    about = (project / 'docs' / 'about.md').read_text(encoding='utf-8')
    assert 'lfr-tunnel is a community project maintained by acme' in about
    assert '_PLACEHOLDER>' not in about

    upstream = '.agents/templates/docs-profiles/liferay/liferay-blue.css'
    assert mappings == [('docs/assets/stylesheets/liferay-blue.css', upstream)]
    reference = project / '.agents' / 'TEMPLATE_REF.md'
    assert record_path_mappings(project, mappings) is True
    assert record_path_mappings(project, mappings) is True      # idempotent
    text = reference.read_text(encoding='utf-8')
    assert text.count(upstream) == 1
    section = text.split('## Path mapping', 1)[1].split('\n---', 1)[0]
    assert '- _None recorded._' not in section and upstream in section, (
        "the mapping goes in place of the placeholder, inside its own section")
    assert '\n\n\n' not in text, "a double blank line fails the adopter's markdownlint (MD012)"
    assert parse_path_mappings(text) == {upstream: 'docs/assets/stylesheets/liferay-blue.css'}


def test_liferay_profile_dry_run_writes_nothing(tmp_path):
    from bootstrap_template import apply_docs_profile, record_path_mappings

    project = _seed_profile_project(tmp_path)
    before = {p: p.read_bytes() for p in project.rglob('*') if p.is_file()}
    mappings = apply_docs_profile(project, 'liferay', 'demo', repo_owner='acme', dry_run=True)
    record_path_mappings(project, mappings, dry_run=True)
    after = {p: p.read_bytes() for p in project.rglob('*') if p.is_file()}
    assert before == after


def test_cleanup_removes_the_shared_docs_files_too(tmp_path):
    from bootstrap_template import clean_docs_site_scaffold

    project = _seed_docs_scaffold(tmp_path)
    (project / 'overrides' / 'partials').mkdir(parents=True)
    (project / 'overrides' / 'partials' / 'copyright.html').write_text('x', encoding='utf-8')
    (project / 'scripts').mkdir()
    (project / 'scripts' / 'mkdocs_github_alerts.py').write_text('x', encoding='utf-8')
    (project / 'scripts' / 'check_docs_rendered.py').write_text('x', encoding='utf-8')
    (project / 'docs' / 'about.md').write_text('x', encoding='utf-8')
    (project / '.agents' / 'templates' / 'docs-profiles' / 'liferay').mkdir(parents=True)

    removed = clean_docs_site_scaffold(project, docs_site=False)
    for rel in ('overrides', 'scripts/mkdocs_github_alerts.py', 'scripts/check_docs_rendered.py',
                'docs/about.md', '.agents/templates/docs-profiles'):
        assert rel in removed and not (project / rel).exists()


def test_docs_workflow_checks_the_build_before_the_upload():
    steps = load_yaml_ignoring_unknown_tags(DOCS_WORKFLOW)['jobs']['build']['steps']
    runs = [step.get('run', '') or step.get('uses', '') for step in steps]
    check = next(i for i, r in enumerate(runs) if 'check_docs_rendered.py' in r)
    drift = next(i for i, r in enumerate(runs) if 'check_template_drift.py --docs-site' in r)
    upload = next(i for i, r in enumerate(runs) if 'upload-pages-artifact' in r)
    build = next(i for i, r in enumerate(runs) if 'mkdocs build' in r)
    assert build < check < upload and drift < upload


# --- End to end: real builds through the real hook and overrides ------------

def _build(project: Path, site: Path):
    return subprocess.run([sys.executable, '-m', 'mkdocs', 'build', '--site-dir', str(site)],
                          cwd=project, capture_output=True, text=True, check=False)


@needs_mkdocs
def test_the_template_site_passes_its_own_rendered_check(tmp_path):
    (DOCS_DIR / GENERATED_HOME_PAGE).write_text(
        (ROOT_DIR / 'README.md').read_text(encoding='utf-8'), encoding='utf-8')
    try:
        result = _build(ROOT_DIR, tmp_path / '_site')
    finally:
        (DOCS_DIR / GENERATED_HOME_PAGE).unlink(missing_ok=True)
    assert result.returncode == 0, result.stderr
    check = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / 'check_docs_rendered.py'), str(tmp_path / '_site'),
         '--config', str(MKDOCS_CONFIG)], capture_output=True, text=True, check=False)
    assert check.returncode == 0, check.stdout


def liferay_profile_project(tmp_path: Path) -> Path:
    """A copy of the template's docs site with the Liferay profile bootstrapped into it, as an
    adopter's repository looks before its home page is written."""
    import shutil
    from bootstrap_template import apply_docs_profile, enable_docs_site

    project = tmp_path / 'project'
    shutil.copytree(ROOT_DIR / 'docs', project / 'docs',
                    ignore=shutil.ignore_patterns('TEMPLATE_GUIDE.md', 'index.md'))
    shutil.copytree(ROOT_DIR / 'overrides', project / 'overrides')
    shutil.copytree(ROOT_DIR / '.agents' / 'templates' / 'docs-profiles',
                    project / '.agents' / 'templates' / 'docs-profiles')
    (project / 'scripts').mkdir()
    for name in ('mkdocs_github_alerts.py', 'check_docs_rendered.py'):
        shutil.copyfile(SCRIPTS_DIR / name, project / 'scripts' / name)
    (project / '.github' / 'workflows').mkdir(parents=True)
    shutil.copyfile(DOCS_WORKFLOW, project / '.github' / 'workflows' / 'docs.yml')
    shutil.copyfile(MKDOCS_CONFIG, project / 'mkdocs.yml')

    enable_docs_site(project, project_name='lfr-tunnel', repo_owner='peterrichards-lr')
    apply_docs_profile(project, 'liferay', 'Liferay Tunnel', repo_owner='peterrichards-lr')
    return project


@needs_mkdocs
def test_a_liferay_profile_site_builds_and_holds_to_the_standard(tmp_path):
    """Bootstrap the profile into a copy, write a conforming home page, build, check -- then
    break the home page and watch the same check fail (the control)."""
    project = liferay_profile_project(tmp_path)
    index = project / 'docs' / 'index.md'

    # A fresh profile site, before anyone has written its home page, must deploy: the profile
    # ships the notice and layout checks off (review of #136).
    index.write_text("# Liferay Tunnel\n\nA new project.\n\n---\n"
                     "*Last Updated: 2026-10-15* | *Last Reviewed: 2026-10-15*\n", encoding='utf-8')
    fresh = _build(project, tmp_path / 'site-fresh')
    assert fresh.returncode == 0, fresh.stderr
    fresh_check = subprocess.run(
        [sys.executable, str(project / 'scripts' / 'check_docs_rendered.py'),
         str(tmp_path / 'site-fresh'), '--config', str(project / 'mkdocs.yml')],
        capture_output=True, text=True, check=False)
    assert fresh_check.returncode == 0, fresh_check.stdout

    config = project / 'mkdocs.yml'
    config.write_text(turn_on_profile_checks(config.read_text(encoding='utf-8')), encoding='utf-8')

    rows = '\n'.join(
        f'| {name} | You are here. {desc} |' if name == 'Liferay Tunnel'
        else f'| [{name}]({url}) | {desc} |' for name, url, desc in RELATED_ROWS)
    home = (
        "# Liferay Tunnel documentation\n\nSecurely expose a local site.\n\n"
        "> [!NOTE]\n"
        "> ℹ️ **Community project** — not an official Liferay product and not covered by "
        "Liferay Support. [About this project](about.md)\n\n"
        "## I want to…\n\n| I want to… | Go to |\n|---|---|\n"
        "| Publish the docs | [Publish](how-to/publish-the-documentation-site.md) |\n\n"
        "## By subject\n\n### Guides\n\n- [Publish](how-to/publish-the-documentation-site.md)\n\n"
        "## Related Liferay tools\n\n" + RELATED_INTRO + "\n\n| Tool | What it does |\n|---|---|\n"
        + rows + "\n\n---\n*Last Updated: 2026-10-15* | *Last Reviewed: 2026-10-15*\n")

    def build_and_check(markdown):
        index.write_text(markdown, encoding='utf-8')
        site = tmp_path / f'site-{len(list(tmp_path.iterdir()))}'
        built = _build(project, site)
        assert built.returncode == 0, built.stderr
        return subprocess.run(
            [sys.executable, str(project / 'scripts' / 'check_docs_rendered.py'), str(site),
             '--config', str(project / 'mkdocs.yml')],
            capture_output=True, text=True, check=False)

    good = build_and_check(home)
    assert good.returncode == 0, good.stdout
    assert 'HOME-LAYOUT' in good.stdout and 'NO-NOTICE' in good.stdout

    broken = build_and_check(home.replace('ℹ️ **Community project** — not', 'Not')
                             .replace('## By subject', '## 📖 By subject'))
    assert broken.returncode == 1
    assert '[NO-NOTICE]' in broken.stdout and '[HOME-LAYOUT]' in broken.stdout


# --- Regressions from the review of #136 -------------------------------------

def test_social_check_accepts_a_site_url_without_its_trailing_slash(tmp_path, capsys):
    """MkDocs adds the slash before the template sees site_url; the check must too."""
    site = _write_site(tmp_path)
    (site / 'assets').mkdir()
    (site / 'assets' / 'social.png').write_bytes(b'png')
    (site / 'assets' / 'apple-touch-icon.png').write_bytes(b'png')
    url = 'https://acme.github.io/demo/assets/social.png'
    tag = (f'<meta property="og:image" content="{url}">'
           '<meta name="twitter:card" content="summary_large_image">'
           f'<meta name="twitter:image" content="{url}">'
           '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">')
    for page in site.rglob('*.html'):
        html = page.read_text(encoding='utf-8').replace('<html><body>', '<html><head><body>')
        page.write_text(html.replace('<head>', '<head>' + tag, 1), encoding='utf-8')
    config = {**_liferay_config(), 'site_url': 'https://acme.github.io/demo',
              'extra': {**_liferay_config()['extra'], 'social_image': 'assets/social.png'}}
    code, out = _run_check(site, config, capsys)
    assert code == 0, out
    assert 'MISSING-SOCIAL' in out, "a configured social check is named as having run"


def test_an_important_callout_before_the_notice_does_not_hide_it(tmp_path, capsys):
    """[!IMPORTANT] renders as `info` too; the notice is any matching callout above the H2."""
    important = ('<div class="admonition info"><p class="admonition-title">Important</p>'
                 '<p>Read this first.</p></div>')
    home = GOOD_HOME.replace('<div class="admonition info">', important
                             + '<div class="admonition info">', 1)
    code, out = _run_check(_write_site(tmp_path, home=home), _liferay_config(), capsys)
    assert code == 0, out


def test_the_pass_line_names_only_the_checks_that_ran(tmp_path, capsys):
    code, out = _run_check(_write_site(tmp_path, home='<h1>demo</h1>'), {'site_name': 'demo'},
                           capsys)
    assert code == 0, out
    assert 'MISSING-SOCIAL' not in out and 'MISSING-VERIFICATION' not in out


def test_a_proper_noun_mid_label_passes_only_when_listed(tmp_path, capsys):
    """Acronyms and inner-capital names pass by shape; "Liferay" needs proper_nouns."""
    site = _write_site(tmp_path, nested='Expose Liferay SE demos to InfoSec reviewers')
    code, out = _run_check(site, _liferay_config(), capsys)
    assert code == 0, out
    config = _liferay_config()
    config['extra']['docs_standard'].pop('proper_nouns')
    code, out = _run_check(site, config, capsys)
    assert code == 1 and 'title case' in out
