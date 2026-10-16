"""
test_docs_social.py - MISSING-SOCIAL covers everything overrides/main.html emits

ai-agent-template#146: the check asserted og:image and nothing else, so a broken twitter:card,
twitter:image, SVG favicon, theme.favicon or apple-touch-icon left X/Slack/Teams previews and
browser icons failing silently with CI green. Each part is checked only when it is configured,
and a site that configures none of them is not checked at all.

The hand-written pages run everywhere. The real build, through the shared overrides/main.html,
runs where mkdocs-material is installed, and removes each tag and each file in turn: a check
that passes its own mutation is not a check.

A dedicated module rather than an addition to tests/test_docs_site.py, so parallel docs-site
work does not conflict on one file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / 'scripts'))

from check_docs_rendered import check_social, run  # noqa: E402

STANDARD_SKILL = ROOT_DIR / '.agents' / 'skills' / 'docs-site-standard' / 'SKILL.md'
SITE_URL = 'https://acme.github.io/demo/'
IMAGE = 'assets/social-preview.png'
URL = SITE_URL + IMAGE
FILES = (IMAGE, 'assets/favicon.svg', 'assets/favicon.png', 'assets/apple-touch-icon.png')

needs_mkdocs = pytest.mark.skipif(
    subprocess.run([sys.executable, '-c', 'import mkdocs, material'],
                   capture_output=True).returncode != 0,
    reason="mkdocs-material is not installed; requirements-docs.txt is deliberately not part "
           "of the language-agnostic quality gate")

# What overrides/main.html and Material's base.html emit for a nested page (docs/guide/).
HEAD = (f'<link rel="icon" href="../assets/favicon.png">'
        f'<meta property="og:image" content="{URL}">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:image" content="{URL}">'
        '<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">'
        '<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">')


def _config(**extra):
    return {'site_url': SITE_URL, 'theme': {'favicon': 'assets/favicon.png'},
            'extra': {'social_image': IMAGE, 'favicon_svg': 'assets/favicon.svg', **extra}}


def _site(tmp_path, head=HEAD, files=FILES):
    for rel in files:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b'x')
    pages = {'guide/index.html': f'<html><head>{head}</head><body></body></html>'}
    return tmp_path, pages


def test_everything_configured_and_present_passes(tmp_path):
    site, pages = _site(tmp_path)
    assert check_social(site, pages, _config()) == []


@pytest.mark.parametrize('label, mutate, expected', [
    ('no twitter:image', lambda h: h.replace(f'<meta name="twitter:image" content="{URL}">', ''),
     'twitter:image is None'),
    ('a twitter:image that differs from og:image',
     lambda h: h.replace(f'name="twitter:image" content="{URL}"',
                         'name="twitter:image" content="https://acme.github.io/old.png"'),
     'not the og:image'),
    ('twitter:card summary', lambda h: h.replace('summary_large_image', 'summary'),
     "twitter:card is 'summary'"),
    ('no og:image', lambda h: h.replace(f'<meta property="og:image" content="{URL}">', ''),
     'no og:image'),
    ('no SVG favicon link', lambda h: h.replace(
        '<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">', ''),
     'no <link> for the SVG favicon'),
    ('no theme.favicon link',
     lambda h: h.replace('<link rel="icon" href="../assets/favicon.png">', ''),
     'no <link> for the theme.favicon icon'),
    ('no apple-touch-icon link',
     lambda h: h.replace('<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">', ''),
     'no <link> for the apple-touch-icon'),
    ('an icon link that 404s from a nested page',
     lambda h: h.replace('href="../assets/favicon.svg"', 'href="assets/favicon.svg"'),
     'resolves to /guide/assets/favicon.svg'),
])
def test_each_broken_tag_fails(tmp_path, label, mutate, expected):
    site, pages = _site(tmp_path, head=mutate(HEAD))
    problems = check_social(site, pages, _config())
    assert any(expected in p for p in problems), f"{label}: {problems}"


@pytest.mark.parametrize('missing', FILES)
def test_each_missing_file_fails(tmp_path, missing):
    site, pages = _site(tmp_path, files=[f for f in FILES if f != missing])
    problems = check_social(site, pages, _config())
    assert any(f'{missing} is not in the build' in p for p in problems), problems


def test_the_404_pages_absolute_links_resolve_under_the_site_path(tmp_path):
    """404.html is served at every depth, so MkDocs links it absolute under site_url's path."""
    head = HEAD.replace('href="../', 'href="/demo/')
    site, _ = _site(tmp_path)
    pages = {'404.html': f'<html><head>{head}</head><body></body></html>'}
    assert check_social(site, pages, _config()) == []
    pages = {'404.html': pages['404.html'].replace('/demo/assets/favicon.svg', '/assets/x.svg')}
    assert check_social(site, pages, _config()), "a wrong absolute link still fails"


def test_only_the_configured_parts_are_checked(tmp_path):
    """No favicon_svg and no theme.favicon: neither link is asked for."""
    head = HEAD.replace('<link rel="icon" href="../assets/favicon.png">', '').replace(
        '<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">', '')
    site, pages = _site(tmp_path, head=head, files=(IMAGE, 'assets/apple-touch-icon.png'))
    assert check_social(site, pages, {'site_url': SITE_URL,
                                      'extra': {'social_image': IMAGE}}) == []


def test_icons_are_checked_without_a_social_image(tmp_path):
    head = HEAD.replace('<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">', '')
    site, pages = _site(tmp_path, head=head)
    problems = check_social(site, pages, {'extra': {'favicon_svg': 'assets/favicon.svg'}})
    assert any('SVG favicon' in p for p in problems), problems
    assert not any('og:image' in p or 'twitter' in p for p in problems), problems


def test_a_site_that_configures_none_of_it_is_not_checked(tmp_path, capsys):
    """Unchanged for a site with no social image and no icons: the template's own site."""
    for rel in ('index.html', 'a/index.html', 'b/index.html', 'c/index.html', 'd/index.html'):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text('<html><head></head><body></body></html>', encoding='utf-8')
    assert check_social(tmp_path, {'index.html': ''}, {'site_name': 'demo'}) == []
    run(tmp_path, {'site_name': 'demo'})
    assert 'MISSING-SOCIAL' not in capsys.readouterr().out.split('✅')[-1]


def test_the_skill_says_what_missing_social_covers():
    row = next(line for line in STANDARD_SKILL.read_text(encoding='utf-8').splitlines()
               if line.startswith('| `MISSING-SOCIAL`'))
    for part in ('twitter:card', 'twitter:image', 'favicon_svg', 'theme.favicon',
                 'apple-touch-icon'):
        assert part in row, f"the skill's MISSING-SOCIAL row does not mention {part}"


# --- A real build, through the shared overrides/main.html ----------------------

MAIN_HTML_LINES = {
    'twitter:image': '<meta name="twitter:image"',
    'twitter:card': '<meta name="twitter:card"',
    'SVG favicon': '<link rel="icon" type="image/svg+xml"',
    'apple-touch-icon': '<link rel="apple-touch-icon"',
}


def _build(tmp_path, drop_line=None, drop_file=None):
    project = tmp_path / 'project'
    shutil.copytree(ROOT_DIR / 'overrides', project / 'overrides')
    main = project / 'overrides' / 'main.html'
    if drop_line:
        main.write_text(''.join(line for line in main.read_text(encoding='utf-8')
                                .splitlines(keepends=True) if drop_line not in line),
                        encoding='utf-8')
    docs = project / 'docs'
    for rel in ('index.md', 'guide/index.md'):
        (docs / rel).parent.mkdir(parents=True, exist_ok=True)
        (docs / rel).write_text('# Page\n', encoding='utf-8')
    for rel in FILES:
        if rel != drop_file:
            (docs / rel).parent.mkdir(parents=True, exist_ok=True)
            (docs / rel).write_bytes(b'x')
    (project / 'mkdocs.yml').write_text(
        f'site_name: demo\nsite_url: {SITE_URL}\n'
        'theme:\n  name: material\n  custom_dir: overrides\n  favicon: assets/favicon.png\n'
        f'extra:\n  social_image: {IMAGE}\n  favicon_svg: assets/favicon.svg\n',
        encoding='utf-8')
    built = subprocess.run([sys.executable, '-m', 'mkdocs', 'build', '-q', '--site-dir', '_site'],
                           cwd=project, capture_output=True, text=True, check=False)
    assert built.returncode == 0, built.stderr
    site = project / '_site'
    pages = {p.relative_to(site).as_posix(): p.read_text(encoding='utf-8')
             for p in site.rglob('*.html')}
    return site, pages


@needs_mkdocs
def test_a_real_build_through_the_shared_override_passes(tmp_path):
    site, pages = _build(tmp_path)
    assert 'guide/index.html' in pages
    assert check_social(site, pages, _config()) == []


@needs_mkdocs
@pytest.mark.parametrize('part', sorted(MAIN_HTML_LINES))
def test_a_real_build_fails_when_the_override_drops_a_tag(tmp_path, part):
    site, pages = _build(tmp_path, drop_line=MAIN_HTML_LINES[part])
    problems = check_social(site, pages, _config())
    assert problems and all(part.split()[-1].lower() in p.lower() for p in problems), problems


@needs_mkdocs
@pytest.mark.parametrize('missing', FILES)
def test_a_real_build_fails_when_a_file_is_missing(tmp_path, missing):
    site, pages = _build(tmp_path, drop_file=missing)
    problems = check_social(site, pages, _config())
    assert any(f'{missing} is not in the build' in p for p in problems), problems
