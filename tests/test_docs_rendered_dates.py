"""
test_docs_rendered_dates.py - UNDATED-PAGE accepts a git-generated "Last update" (#142)

`check_docs_rendered.py`'s UNDATED-PAGE asserts that a reader can see when a page was last
updated and when it was last reviewed. A site may type both dates into the page body, or let
mkdocs-git-revision-date-localized-plugin generate the first from git, in which case Material
shows it in its source-file aside and only "Last Reviewed" is in the body. Both renderings
pass; a page that shows only one of the two dates still fails.

The aside markup below is copied from a real build (mkdocs 1.6.1, mkdocs-material 9.7.7,
mkdocs-git-revision-date-localized-plugin 1.6.0), with the inline SVG elided. Its icon title is
Material's `source.file.date.updated` translation, so it is localised ("Letztes Update" in
German), which is why the check matches the structure and not the English word.

A dedicated module rather than additions to tests/test_docs_site.py, whose helpers it reuses:
appending to a shared test module is this repository's usual merge-conflict source.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from test_docs_site import (  # noqa: E402
    STANDARD_SKILL, _liferay_config, _run_check, _write_site)

REVIEWED_ONLY = '<p><em>Last Reviewed: 2026-09-17</em></p>'


def _fact(title, date_html):
    return ('<span class="md-source-file__fact">\n'
            f'    <span class="md-icon" title="{title}">\n      <svg></svg>\n    </span>\n'
            f'    {date_html}\n  </span>\n')


def _aside(*facts):
    return '<aside class="md-source-file">\n' + ''.join(facts) + '</aside>\n'


DATE_SPAN = ('<span class="git-revision-date-localized-plugin '
             'git-revision-date-localized-plugin-date" title="October 15, 2026 07:21:01 UTC">'
             'October 15, 2026</span>')
UPDATED_EN = _aside(_fact('Last update', DATE_SPAN))
UPDATED_DE = _aside(_fact('Letztes Update',
                          DATE_SPAN.replace('October 15, 2026', '15. Oktober 2026')))
UPDATED_TIMEAGO = _aside(_fact(
    'Last update',
    '<span class="git-revision-date-localized-plugin git-revision-date-localized-plugin-timeago" '
    'title="October 15, 2026"><span class="timeago" datetime="2026-10-15T07:21:01+00:00" '
    'locale="en"></span></span><span class="git-revision-date-localized-plugin '
    'git-revision-date-localized-plugin-iso_date" title="October 15, 2026">2026-10-15</span>'))
CONTRIBUTORS_ONLY = _aside(_fact('Contributors', '<nav>Ada Lovelace, Alan Turing</nav>'))


@pytest.mark.parametrize('label, footer', [
    ('an English "Last update" aside', UPDATED_EN),
    ('a German "Letztes Update" aside: the title is localised', UPDATED_DE),
    ('a timeago date, whose visible text is filled in by JavaScript', UPDATED_TIMEAGO),
])
def test_a_generated_last_update_with_a_typed_last_reviewed_is_dated(tmp_path, capsys, label,
                                                                    footer):
    site = _write_site(tmp_path, nested_footer=footer + REVIEWED_ONLY)
    code, out = _run_check(site, _liferay_config(), capsys)
    assert code == 0, f"{label}: the check failed\n{out}"
    assert 'UNDATED-PAGE' in out, "UNDATED-PAGE is named as having run"


@pytest.mark.parametrize('label, footer, expected', [
    ('the aside with no Last Reviewed', UPDATED_EN, 'no Last Reviewed'),
    ('Last Reviewed with no aside', REVIEWED_ONLY, 'no Last Updated'),
    ('Last Reviewed with an aside that carries only contributors',
     CONTRIBUTORS_ONLY + REVIEWED_ONLY, 'no Last Updated'),
    ('neither date', '', 'no Last Updated / Last Reviewed'),
])
def test_a_page_showing_only_one_date_is_undated(tmp_path, capsys, label, footer, expected):
    site = _write_site(tmp_path, nested_footer=footer)
    code, out = _run_check(site, _liferay_config(), capsys)
    assert code == 1, f"{label}: the check passed\n{out}"
    assert '[UNDATED-PAGE]' in out and 'guides/setup/index.html' in out, out
    assert expected in out, f"{label}: expected {expected!r} in\n{out}"


def test_the_standard_skill_states_both_accepted_renderings():
    skill = STANDARD_SKILL.read_text(encoding='utf-8')
    row = next(line for line in skill.splitlines() if line.startswith('| `UNDATED-PAGE`'))
    assert 'md-source-file' in row and 'Last Reviewed' in row, row
    assert 'mkdocs-git-revision-date-localized-plugin' in skill
    assert 'both are allowed' in skill, (
        "the skill must say that typing both dates and generating Last updated are both allowed")


# --- End to end: a real build with the plugin ---------------------------------

needs_revision_plugin = pytest.mark.skipif(
    subprocess.run([sys.executable, '-c',
                    'import mkdocs, material, mkdocs_git_revision_date_localized_plugin'],
                   capture_output=True).returncode != 0,
    reason="mkdocs-material or mkdocs-git-revision-date-localized-plugin is not installed")

PAGES = {'index.md': '# Home', 'guide.md': '# Guide', 'about.md': '# About these docs'}


def _built_pages(project: Path, language: str, plugin: bool) -> dict:
    """Build a three-page Material site in a fresh git repository and return its pages."""
    (project / 'docs').mkdir(parents=True, exist_ok=True)
    for name, heading in PAGES.items():
        (project / 'docs' / name).write_text(
            f"{heading}\n\nText.\n\n*Last Reviewed: 2026-09-17*\n", encoding='utf-8')
    config = f"site_name: fixture\ntheme:\n  name: material\n  language: {language}\n"
    if plugin:
        config += "plugins:\n  - git-revision-date-localized\n"
    (project / 'mkdocs.yml').write_text(config, encoding='utf-8')
    if not (project / '.git').exists():
        for args in (['init', '-q'], ['add', '-A'],
                     ['-c', 'user.name=fixture', '-c', 'user.email=fixture@example.com',
                      '-c', 'commit.gpgsign=false', 'commit', '-q', '--no-verify', '-m', 'x']):
            subprocess.run(['git', *args], cwd=project, check=True, capture_output=True)
    site = project / f'site-{language}-{plugin}'
    built = subprocess.run([sys.executable, '-m', 'mkdocs', 'build', '--site-dir', str(site)],
                           cwd=project, capture_output=True, text=True, check=False)
    assert built.returncode == 0, built.stderr
    return {p.relative_to(site).as_posix(): p.read_text(encoding='utf-8')
            for p in sorted(site.rglob('*.html'))}


@needs_revision_plugin
@pytest.mark.parametrize('language, title', [('en', 'Last update'), ('de', 'Letztes Update')])
def test_a_real_build_with_the_plugin_is_dated_in_any_language(tmp_path, language, title):
    from check_docs_rendered import check_footers

    pages = _built_pages(tmp_path, language, plugin=True)
    assert f'title="{title}"' in pages['guide/index.html'], (
        "the fixture must exercise Material's own, localised aside")
    assert check_footers(pages) == []


@needs_revision_plugin
def test_a_real_build_without_the_plugin_is_undated(tmp_path):
    """The control: the same pages, with no generated date, fail."""
    from check_docs_rendered import check_footers

    pages = _built_pages(tmp_path, 'en', plugin=False)
    assert 'md-source-file' not in pages['guide/index.html']
    problems = check_footers(pages)
    assert len(problems) == len(PAGES) and all('no Last Updated' in p for p in problems), problems
