"""
test_docs_profile_source.py - The profile marker counts in the source docs_dir, not only the build

v2.6.0 found the Liferay profile by the `docs-profile: liferay` marker in a stylesheet in the
BUILT site (#162). MkDocs' `exclude_docs` keeps a file out of the build while it stays in
docs/ unchanged, so the drift check stays green and the profile went with it. Reproduced on
lfr-tunnel's v2.6.0 build (#179):

1. liferay-blue.css removed from extra_css and excluded, `required` and Google's token deleted:
   exit 0, MISSING-VERIFICATION silently gone.
2. The same exclusion, Google's token swapped for Bing's: exit 0, because `:google` came only
   from the profile.

check_docs_rendered.py now also searches the source docs_dir, resolved from mkdocs.yml as MkDocs
does, so both fail. These run through main() with a real mkdocs.yml and docs/ on disk.

A dedicated module, beside tests/test_profile_marker.py, whose fixtures it reuses.
"""

import copy
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from check_docs_rendered import main  # noqa: E402
from test_docs_required_profile import _met  # noqa: E402
from test_docs_site import (  # noqa: E402
    _build, _write_site, liferay_profile_project, needs_mkdocs)
from test_profile_marker import LIFERAY_CSS  # noqa: E402

EXCLUDED = 'assets/stylesheets/liferay-blue.css'


def _project(tmp_path, config, marked_in_docs=True, docs_dir='docs'):
    """A repository as lfr-tunnel's: mkdocs.yml, the stylesheet in docs/ but excluded from the
    build, and the built site, which therefore has no marked stylesheet."""
    root = tmp_path / 'repo'
    root.mkdir()
    if docs_dir != 'docs':
        config['docs_dir'] = docs_dir
    sheet = root / docs_dir / EXCLUDED
    sheet.parent.mkdir(parents=True)
    sheet.write_text(LIFERAY_CSS.read_text(encoding='utf-8') if marked_in_docs else ':root {}\n',
                     encoding='utf-8')
    (root / 'mkdocs.yml').write_text(yaml.safe_dump(config), encoding='utf-8')
    site = _write_site(root / '_site')
    assert not list(site.rglob('*.css')), "the excluded stylesheet must not be in the build"
    return root, site


def _excluded(config):
    """The edits #179 found together: dropped from extra_css, excluded, `required` deleted."""
    config = copy.deepcopy(config)
    config['extra_css'] = []
    config['exclude_docs'] = EXCLUDED
    config['extra']['docs_standard'].pop('required', None)
    return config


def _check(root, site, capsys):
    code = main([str(site), '--config', str(root / 'mkdocs.yml')])
    return code, capsys.readouterr().out


def test_row_1_excluded_stylesheet_and_deleted_token_fail(tmp_path, capsys):
    config = _excluded(_met())
    del config['extra']['google_site_verification']
    code, out = _check(*_project(tmp_path, config), capsys)
    assert code == 1, out
    assert '[MISSING-VERIFICATION]' in out and 'required by the Liferay profile' in out, out


def test_row_2_excluded_stylesheet_and_bing_for_google_fail(tmp_path, capsys):
    config = _excluded(_met())
    del config['extra']['google_site_verification']
    config['extra']['bing_site_verification'] = 'BING'
    code, out = _check(*_project(tmp_path, config), capsys)
    assert code == 1, out
    assert '[MISSING-VERIFICATION:google]' in out, out


def test_a_custom_docs_dir_is_searched(tmp_path, capsys):
    """docs_dir resolves from mkdocs.yml, relative to the config file, as MkDocs resolves it."""
    config = _excluded(_met())
    del config['extra']['google_site_verification']
    code, out = _check(*_project(tmp_path, config, docs_dir='site-src'), capsys)
    assert code == 1 and '[MISSING-VERIFICATION]' in out, out


def test_control_no_marked_stylesheet_anywhere_is_no_profile(tmp_path, capsys):
    """The narrowness control: an unmarked stylesheet in docs/ applies no profile, so nothing
    requires the deleted token."""
    config = _excluded(_met())
    del config['extra']['google_site_verification']
    code, out = _check(*_project(tmp_path, config, marked_in_docs=False), capsys)
    assert '[MISSING-VERIFICATION]' not in out, out
    assert 'required by the Liferay profile' not in out, out


@needs_mkdocs
def test_a_real_build_with_the_stylesheet_excluded_still_applies_the_profile(tmp_path):
    """#179 row 1 through a real mkdocs build: the profile stylesheet dropped from extra_css and
    excluded from the build, and the waives deleted (lfr-tunnel waives nothing). The build has
    no marked stylesheet; docs/ still does, so the profile's checks still run."""
    project = liferay_profile_project(tmp_path)
    (project / 'docs' / 'index.md').write_text(
        "# Liferay Tunnel\n\nA new project.\n\n---\n"
        "*Last Updated: 2026-10-19* | *Last Reviewed: 2026-10-19*\n", encoding='utf-8')
    mkdocs_yml = project / 'mkdocs.yml'
    text = mkdocs_yml.read_text(encoding='utf-8')
    entry = re.compile(r'^  - ' + re.escape(EXCLUDED) + r'\b.*\n', re.M)
    assert entry.search(text) and '    waive:\n' in text
    text = entry.sub('', text, count=1)
    text = re.sub(r'\n    waive:\n(?:      .*\n)+', '\n', text, count=1)
    mkdocs_yml.write_text(text + f'\nexclude_docs: |\n  {EXCLUDED}\n', encoding='utf-8')

    built = _build(project, tmp_path / '_site')
    assert built.returncode == 0, built.stderr
    assert not list((tmp_path / '_site').rglob('liferay-blue.css')), "it must be excluded"
    assert (project / 'docs' / EXCLUDED).is_file()

    check = subprocess.run(
        [sys.executable, str(project / 'scripts' / 'check_docs_rendered.py'),
         str(tmp_path / '_site'), '--config', str(mkdocs_yml)],
        capture_output=True, text=True, check=False)
    assert check.returncode == 1, check.stdout
    assert '[MISSING-VERIFICATION]' in check.stdout, check.stdout
    assert 'required by the Liferay profile' in check.stdout, check.stdout
