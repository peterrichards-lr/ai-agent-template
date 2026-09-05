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

    assert concurrency.get('group') == 'pages', (
        "Pages deployments must share the single 'pages' concurrency group")
    assert concurrency.get('cancel-in-progress') is False, (
        "cancel-in-progress must be false: cancelling an in-flight Pages deployment "
        "leaves the live site in a half-applied state")


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
