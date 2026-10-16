"""
test_docs_section_titles.py - Section titles render the same with or without an index page

ai-agent-template#143: with `navigation.indexes`, Material renders a section that has an index
page as a link in the primary text colour, and one without as a label in the secondary colour.
The same stylesheet gave liferay-docker-manager white section titles and lfr-tunnel muted ones.
The shared rule (SECTION_TITLE_RULE, carried by the Liferay profile's liferay-blue.css) gives
the link the label's colour, and SECTION-TITLE in check_docs_rendered.py holds a site to it.

Computed colour is not in static HTML, so what can regress is the two halves the rule depends
on: the stylesheet carrying it, and Material still rendering a section title in the markup it
targets. A string match on the stylesheet catches only the first; the real-build fixture below,
one indexed and one plain section, catches a theme upgrade that renames the markup.

A dedicated module rather than an addition to tests/test_docs_site.py, so parallel docs-site
work does not conflict on one file.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / 'scripts'))

from check_docs_rendered import (  # noqa: E402
    SECTION_TITLE_RULE, SectionTitles, _compact_css, check_section_titles)

LIFERAY_CSS = ROOT_DIR / '.agents' / 'templates' / 'docs-profiles' / 'liferay' / 'liferay-blue.css'
STANDARD_SKILL = ROOT_DIR / '.agents' / 'skills' / 'docs-site-standard' / 'SKILL.md'
CSS_PATH = 'assets/stylesheets/liferay-blue.css'

needs_mkdocs = pytest.mark.skipif(
    subprocess.run([sys.executable, '-c', 'import mkdocs, material'],
                   capture_output=True).returncode != 0,
    reason="mkdocs-material is not installed; requirements-docs.txt is deliberately not part "
           "of the language-agnostic quality gate")

# Material 9.7.7's primary nav, as `mkdocs build` renders it, trimmed to the section titles.
INDEXED = ('<li class="md-nav__item md-nav__item--section md-nav__item--nested">'
           '<input class="md-nav__toggle md-toggle" type="checkbox" id="__nav_2">'
           '<div class="md-nav__link md-nav__container">'
           '<a href="tutorials/" class="md-nav__link"><span class="md-ellipsis">Tutorials</span>'
           '</a><label class="md-nav__link" for="__nav_2" id="__nav_2_label">'
           '<span class="md-nav__icon md-icon"></span></label></div>'
           '<nav class="md-nav" data-md-level="1"><label class="md-nav__title" for="__nav_2">'
           'Tutorials</label><ul class="md-nav__list"><li class="md-nav__item">'
           '<a href="tutorials/one/" class="md-nav__link"><span class="md-ellipsis">One</span></a>'
           '</li></ul></nav></li>')
PLAIN = ('<li class="md-nav__item md-nav__item--section md-nav__item--nested">'
         '<input class="md-nav__toggle md-toggle" type="checkbox" id="__nav_3">'
         '<label class="md-nav__link" for="__nav_3" id="__nav_3_label">'
         '<span class="md-ellipsis">Reference</span><span class="md-nav__icon md-icon"></span>'
         '</label><nav class="md-nav" data-md-level="1"><ul class="md-nav__list">'
         '<li class="md-nav__item"><a href="reference/api/" class="md-nav__link">'
         '<span class="md-ellipsis">API</span></a></li></ul></nav></li>')


def _home(*items):
    return ('<html><body><nav class="md-nav md-nav--primary" data-md-level="0">'
            f'<ul class="md-nav__list">{"".join(items)}</ul></nav></body></html>')


def _site(tmp_path, css=None):
    if css is not None:
        (tmp_path / CSS_PATH).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / CSS_PATH).write_text(css, encoding='utf-8')
    return tmp_path


def _without_rule(css):
    start = css.index('@media screen and (min-width: 76.25em)')
    return css[:start] + css[css.index('}\n}', start) + 3:]


def test_the_liferay_stylesheet_carries_the_shared_rule():
    assert _compact_css(SECTION_TITLE_RULE) in _compact_css(
        LIFERAY_CSS.read_text(encoding='utf-8'))


def test_the_rule_matches_however_it_is_spaced_and_only_with_the_whole_selector():
    spaced = SECTION_TITLE_RULE.replace('> ', '>').replace(';', ' ; ') + '  /* note */'
    assert _compact_css(SECTION_TITLE_RULE) == _compact_css(spaced)
    loose = SECTION_TITLE_RULE.replace(':not(:hover):not(.md-nav__link--active)', '')
    assert _compact_css(SECTION_TITLE_RULE) not in _compact_css(loose), (
        "without the guards, hover and the active page lose the link colour")


def test_the_parser_tells_an_indexed_section_from_a_plain_one():
    parser = SectionTitles()
    parser.feed(_home(INDEXED, PLAIN))
    assert parser.sections == [('indexed', 'Tutorials'), ('label', 'Reference')]


def test_an_indexed_and_a_plain_section_pass_with_the_rule(tmp_path):
    site = _site(tmp_path, LIFERAY_CSS.read_text(encoding='utf-8'))
    problems, indexed = check_section_titles(site, _home(INDEXED, PLAIN),
                                             {'extra_css': [CSS_PATH]})
    assert problems == [] and indexed == ['Tutorials']


def test_an_indexed_section_fails_without_the_rule(tmp_path):
    site = _site(tmp_path, _without_rule(LIFERAY_CSS.read_text(encoding='utf-8')))
    problems, _ = check_section_titles(site, _home(INDEXED, PLAIN), {'extra_css': [CSS_PATH]})
    assert len(problems) == 1 and "'Tutorials'" in problems[0]
    assert SECTION_TITLE_RULE in problems[0], "the failure gives the rule to add"


def test_a_site_with_no_stylesheet_fails_when_it_has_an_indexed_section(tmp_path):
    problems, _ = check_section_titles(_site(tmp_path), _home(INDEXED, PLAIN), {})
    assert problems and 'extra_css (none)' in problems[0]


def test_a_site_without_index_pages_has_nothing_to_check(tmp_path):
    """Index pages are optional: a site without one does not need the rule."""
    assert check_section_titles(_site(tmp_path), _home(PLAIN, PLAIN), {}) == ([], [])


def test_a_linked_title_the_rule_cannot_reach_fails(tmp_path):
    """A theme upgrade that renames .md-nav__container must not pass silently."""
    renamed = INDEXED.replace('md-nav__container', 'md-nav__wrapper')
    site = _site(tmp_path, LIFERAY_CSS.read_text(encoding='utf-8'))
    problems, indexed = check_section_titles(site, _home(renamed, PLAIN),
                                             {'extra_css': [CSS_PATH]})
    assert indexed == ['Tutorials']
    assert any('does not reach' in p for p in problems), problems


def test_the_table_of_contents_is_not_read_as_a_section():
    toc = ('<nav class="md-nav md-nav--secondary"><ul class="md-nav__list">'
           '<li class="md-nav__item md-nav__item--section"><a class="md-nav__link">H</a></li>'
           '</ul></nav>')
    parser = SectionTitles()
    parser.feed(_home(PLAIN.replace('</label>', '</label>' + toc, 1)))
    assert parser.sections == [('label', 'Reference')]


def test_the_skill_says_index_pages_are_optional_and_render_the_same():
    skill = STANDARD_SKILL.read_text(encoding='utf-8')
    assert 'SECTION-TITLE' in skill
    assert 'Index pages are optional' in skill


@needs_mkdocs
@pytest.mark.parametrize('with_rule', [True, False])
def test_a_real_build_with_one_indexed_and_one_plain_section(tmp_path, with_rule):
    """The fixture the issue asks for: Material's real markup, through the real check."""
    docs = tmp_path / 'docs'
    for rel, text in {'index.md': '# Home\n', 'tutorials/index.md': '# Tutorials\n',
                      'tutorials/one.md': '# One\n', 'reference/api.md': '# API\n'}.items():
        (docs / rel).parent.mkdir(parents=True, exist_ok=True)
        (docs / rel).write_text(text, encoding='utf-8')
    css = LIFERAY_CSS.read_text(encoding='utf-8')
    (docs / CSS_PATH).parent.mkdir(parents=True)
    (docs / CSS_PATH).write_text(css if with_rule else _without_rule(css), encoding='utf-8')
    (tmp_path / 'mkdocs.yml').write_text(
        'site_name: fixture\ntheme:\n  name: material\n'
        '  features: [navigation.sections, navigation.indexes]\n'
        f'extra_css: [{CSS_PATH}]\n'
        'nav:\n  - Home: index.md\n'
        '  - Tutorials:\n      - tutorials/index.md\n      - One: tutorials/one.md\n'
        '  - Reference:\n      - API: reference/api.md\n', encoding='utf-8')
    built = subprocess.run([sys.executable, '-m', 'mkdocs', 'build', '-q', '--site-dir', '_site'],
                           cwd=tmp_path, capture_output=True, text=True, check=False)
    assert built.returncode == 0, built.stderr

    site = tmp_path / '_site'
    home = (site / 'index.html').read_text(encoding='utf-8')
    parser = SectionTitles()
    parser.feed(home)
    assert parser.sections == [('indexed', 'Tutorials'), ('label', 'Reference')], (
        "Material no longer renders section titles in the markup SECTION_TITLE_RULE targets")
    problems, _ = check_section_titles(site, home, {'extra_css': [CSS_PATH]})
    assert (problems == []) is with_rule, problems
