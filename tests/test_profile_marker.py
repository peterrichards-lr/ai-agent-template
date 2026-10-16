"""
test_profile_marker.py - The profile stylesheet is identified by its marker, not its name

The Liferay profile's checks hung off `liferay-blue.css` by name: in extra_css for the rendered
check, and at docs/assets/stylesheets/ for the drift check's unmapped-stylesheet guard. So:

- `extra_css: [assets/stylesheets/liferay-blue.css?v=2]` hid the profile and its four required
  checks (lfr-tunnel's case 4 on #155; #164 (b));
- dropping the stylesheet from extra_css did the same (case 2 on #155);
- renaming the stylesheet, deleting its mapping and editing it gave "No drift", exit 0 (#162,
  from the review of lfr-tunnel#2410).

The stylesheet now carries a `docs-profile: liferay` line, and both checks find the file by
it, wherever it is and whatever it is called.

A dedicated module, beside tests/test_docs_required_profile.py and tests/test_template_drift.py,
whose helpers and fixtures it reuses.
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import check_docs_rendered  # noqa: E402
import check_template_drift  # noqa: E402
from check_docs_rendered import check_required, profile_required  # noqa: E402
from test_docs_required_profile import PROFILE_CHECKS, _delete, _met  # noqa: E402
from test_docs_site import _liferay_config, _run_check, _write_site  # noqa: E402
from test_template_drift import (  # noqa: E402,F401  (docs_upstream is a fixture)
    CSS_LOCAL, CSS_UPSTREAM, adopter_with_docs_files, docs_upstream, main, run_git,
    write_reference_file)

ROOT_DIR = Path(__file__).parent.parent
LIFERAY_CSS = ROOT_DIR / CSS_UPSTREAM
LIFERAY = ('the Liferay profile', PROFILE_CHECKS)


def _site_with_css(tmp_path, rel, body=None):
    site = tmp_path / 'site'
    (site / rel).parent.mkdir(parents=True, exist_ok=True)
    (site / rel).write_text(body if body is not None else LIFERAY_CSS.read_text(encoding='utf-8'),
                            encoding='utf-8')
    return site


def _unprofiled(config):
    """The site's config with nothing naming the profile stylesheet."""
    config = copy.deepcopy(config)
    config['extra_css'] = []
    return config


# --- The marker itself ---------------------------------------------------------------------

def test_the_shipped_stylesheet_carries_the_marker_once():
    text = LIFERAY_CSS.read_text(encoding='utf-8')
    assert check_docs_rendered.PROFILE_MARKER.findall(text) == ['liferay']


def test_both_checks_read_the_marker_the_same_way():
    assert (check_docs_rendered.PROFILE_MARKER.pattern
            == check_template_drift.PROFILE_MARKER.pattern)


# --- The rendered check: which site is the profile -----------------------------------------

@pytest.mark.parametrize('rel', [
    'assets/stylesheets/liferay-blue.css',     # where bootstrap puts it
    'assets/stylesheets/brand.css',            # renamed
    'css/theme/palette.css',                   # moved and renamed
])
def test_the_profile_is_found_by_its_marker_wherever_the_file_is(tmp_path, rel):
    """No extra_css entry at all: lfr-tunnel's case 2 (dropped from extra_css) and #164 (b)."""
    site = _site_with_css(tmp_path, rel)
    assert profile_required(_unprofiled(_met()), site) == LIFERAY


def test_a_suffixed_extra_css_entry_still_finds_the_profile(tmp_path):
    site = _site_with_css(tmp_path, 'assets/stylesheets/liferay-blue.css')
    config = _met()
    config['extra_css'] = ['assets/stylesheets/liferay-blue.css?v=2']
    assert profile_required(config, site) == LIFERAY


def test_a_stylesheet_without_the_marker_is_not_the_profile(tmp_path):
    site = _site_with_css(tmp_path, 'assets/stylesheets/site.css', ':root { --x: 1; }\n')
    assert profile_required(_unprofiled(_met()), site) == (None, ())


def test_an_unknown_profile_marker_is_not_a_profile(tmp_path):
    site = _site_with_css(tmp_path, 'assets/stylesheets/x.css', '/*\n * docs-profile: acme\n */\n')
    assert profile_required(_unprofiled(_met()), site) == (None, ())


def test_a_copy_from_before_the_marker_is_still_known_by_its_name(tmp_path):
    """Until a site syncs the marked stylesheet, extra_css still names the profile."""
    site = _site_with_css(tmp_path, 'assets/stylesheets/liferay-blue.css', ':root {}\n')
    assert profile_required(_met(), site) == LIFERAY


def test_a_renamed_stylesheet_and_deleted_required_and_token_still_fail(tmp_path, capsys):
    """The combination lfr-tunnel tried, through the real check: the profile stylesheet renamed
    and dropped from extra_css, `required` deleted, the Google token deleted."""
    site = _write_site(tmp_path)
    (site / 'assets' / 'stylesheets').mkdir(parents=True)
    (site / 'assets' / 'stylesheets' / 'brand.css').write_text(
        LIFERAY_CSS.read_text(encoding='utf-8'), encoding='utf-8')
    config = _unprofiled(_liferay_config())
    config['extra']['docs_standard'].pop('required', None)
    config['extra']['docs_standard'].pop('waive', None)   # lfr-tunnel waives nothing
    code, out = _run_check(site, config, capsys)
    assert code == 1 and '[MISSING-VERIFICATION]' in out, out
    assert 'required by the Liferay profile' in out, out


def test_without_a_build_the_marker_is_not_needed(tmp_path):
    """check_required without a site falls back to extra_css, as before."""
    assert 'MISSING-VERIFICATION' in check_required(
        _delete(_met(), 'extra.google_site_verification'), set())


# --- The drift check: an unmapped copy, renamed or moved (#162) ----------------------------

@pytest.fixture()
def marked_upstream(docs_upstream):
    """docs_upstream, its profile stylesheet carrying the marker as the shipped one does."""
    css = docs_upstream['path'] / CSS_UPSTREAM
    css.write_text('/*\n * docs-profile: liferay\n */\n:root {}\n', encoding='utf-8')
    run_git(['commit', '--quiet', '-am', 'marker'], docs_upstream['path'])
    docs_upstream['commit'] = run_git(['rev-parse', 'HEAD'],
                                      docs_upstream['path']).stdout.strip()
    return docs_upstream


def _adopter(tmp_path, upstream, local_css, mapped):
    local_root = adopter_with_docs_files(tmp_path / 'local', upstream['path'],
                                         at={CSS_UPSTREAM: local_css})
    reference = write_reference_file(local_root, upstream['url'], upstream['commit'])
    if mapped:
        text = reference.read_text(encoding='utf-8')
        reference.write_text(text.replace(
            '## Known drift', f'## Path mapping\n\n- `{local_css}` ← `{CSS_UPSTREAM}`\n\n'
            '## Known drift'), encoding='utf-8')
    return local_root


@pytest.mark.parametrize('local_css', [
    'docs/assets/stylesheets/brand.css',   # renamed
    'docs/css/palette.css',                # moved and renamed
])
def test_a_renamed_unmapped_edited_stylesheet_exits_3(
        tmp_path, marked_upstream, capsys, local_css):
    """#162: rename, delete the mapping, edit. v2.4.0 said "No drift" and exited 0."""
    local_root = _adopter(tmp_path, marked_upstream, local_css, mapped=False)
    (local_root / local_css).write_text(
        (local_root / local_css).read_text(encoding='utf-8') + '.edited {}\n', encoding='utf-8')
    code = main(['--root', str(local_root), '--docs-site', '--fail-on-drift'])
    captured = capsys.readouterr()
    assert code == 3, captured.out + captured.err
    assert f"- `{local_css}` ← `{CSS_UPSTREAM}`" in captured.out


def test_a_renamed_stylesheet_that_is_mapped_is_compared(tmp_path, marked_upstream, capsys):
    """Mapped, it is compared: an edit to it is drift (exit 2), not "not compared"."""
    local_css = 'docs/assets/stylesheets/brand.css'
    local_root = _adopter(tmp_path, marked_upstream, local_css, mapped=True)
    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 0
    (local_root / local_css).write_text('/*\n * docs-profile: liferay\n */\n.edited {}\n',
                                        encoding='utf-8')
    capsys.readouterr()
    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 2


def test_a_site_stylesheet_without_the_marker_is_left_alone(tmp_path, marked_upstream, capsys):
    local_root = _adopter(tmp_path, marked_upstream, CSS_LOCAL, mapped=True)
    (local_root / 'docs' / 'assets' / 'stylesheets' / 'site.css').write_text(
        '.mine {}\n', encoding='utf-8')
    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 0


def test_a_built_sites_copy_is_not_an_unmapped_stylesheet(tmp_path, marked_upstream, capsys):
    """_site/ holds a marked copy after every docs CI build, before the drift step runs."""
    local_root = _adopter(tmp_path, marked_upstream, CSS_LOCAL, mapped=True)
    built = local_root / '_site' / 'assets' / 'stylesheets' / 'liferay-blue.css'
    built.parent.mkdir(parents=True)
    built.write_text((local_root / CSS_LOCAL).read_text(encoding='utf-8'), encoding='utf-8')
    assert main(['--root', str(local_root), '--docs-site', '--fail-on-drift']) == 0
