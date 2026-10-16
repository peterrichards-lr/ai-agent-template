"""
test_docs_required_checks.py - Required rendered-output checks, and the minimum build size

Covers `extra.docs_standard.required` in scripts/check_docs_rendered.py (ai-agent-template#141).
A check that runs only when mkdocs.yml configures it is switched off by deleting its key, and
the build stays green: lfr-tunnel lost its Search Console verification that way (lfr-tunnel
#2381). A site lists the checks it cannot do without in `required`, and a required check with
no configuration fails instead of being skipped.

Deliberately a separate module from tests/test_docs_site.py, whose synthetic-site helpers it
reuses: parallel branches append to that file, and every merge conflict in this repository's
history came from appending to a shared test module.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from test_docs_site import _liferay_config, _run_check, _write_site  # noqa: E402

PLAIN_HOME = '<h1>demo</h1><p>Hello.</p>'


def _required(*names, **extra):
    """A generic site's config that requires `names`, with any other `extra:` keys given."""
    return {'site_name': 'demo',
            'extra': {**extra, 'docs_standard': {'required': list(names)}}}


@pytest.mark.parametrize('name, missing_key', [
    ('MISSING-VERIFICATION', 'extra.google_site_verification'),
    ('MISSING-SOCIAL', 'extra.social_image'),
    ('NO-NOTICE', 'extra.docs_standard.notice'),
    ('HOME-LAYOUT', 'extra.docs_standard.home_layout'),
])
def test_a_required_check_with_no_configuration_fails_and_names_the_key(
        tmp_path, capsys, name, missing_key):
    site = _write_site(tmp_path, home=PLAIN_HOME)
    code, out = _run_check(site, _required(name), capsys)
    assert code == 1, f"{name} is required and unconfigured, yet the check passed\n{out}"
    assert f'[{name}]' in out, out
    assert missing_key in out, f"the failure must name the missing key {missing_key!r}\n{out}"


def test_without_required_the_same_site_passes(tmp_path, capsys):
    """The control: the site above, with nothing required, skips the unconfigured checks."""
    site = _write_site(tmp_path, home=PLAIN_HOME)
    code, out = _run_check(site, {'site_name': 'demo'}, capsys)
    assert code == 0, out


def test_required_checks_that_are_configured_and_met_pass(tmp_path, capsys):
    config = _liferay_config()
    config['extra']['docs_standard']['required'] = ['NO-NOTICE', 'HOME-LAYOUT']
    code, out = _run_check(_write_site(tmp_path), config, capsys)
    assert code == 0, out
    assert 'HOME-LAYOUT' in out and 'NO-NOTICE' in out


def test_a_required_verification_check_passes_once_configured_and_present(tmp_path, capsys):
    site = _write_site(tmp_path, home=PLAIN_HOME)
    for page in site.rglob('*.html'):
        html = page.read_text(encoding='utf-8')
        page.write_text(html.replace(
            '<head>', '<head><meta name="google-site-verification" content="TOKEN">', 1)
            .replace('<html><body>', '<html><head><meta name="google-site-verification" '
                     'content="TOKEN"></head><body>', 1), encoding='utf-8')
    config = _required('MISSING-VERIFICATION', google_site_verification='TOKEN')
    code, out = _run_check(site, config, capsys)
    assert code == 0, out
    assert 'MISSING-VERIFICATION' in out


def test_an_unknown_name_in_required_fails(tmp_path, capsys):
    """A typo must not quietly require nothing."""
    site = _write_site(tmp_path, home=PLAIN_HOME)
    code, out = _run_check(site, _required('MISSING-VERIFCATION'), capsys)
    assert code == 1, out
    assert '[REQUIRED]' in out and 'MISSING-VERIFCATION' in out


def test_required_must_be_a_list(tmp_path, capsys):
    """`required: HOME-LAYOUT` is a string, and iterating it would require nothing real."""
    site = _write_site(tmp_path, home=PLAIN_HOME)
    config = {'site_name': 'demo', 'extra': {'docs_standard': {'required': 'HOME-LAYOUT'}}}
    code, out = _run_check(site, config, capsys)
    assert code == 1, out
    assert '[REQUIRED]' in out


def test_an_always_run_check_in_required_is_accepted(tmp_path, capsys):
    """NAV runs on every site, so naming it requires nothing more, and is not a mistake."""
    site = _write_site(tmp_path, home=PLAIN_HOME)
    code, out = _run_check(site, _required('NAV'), capsys)
    assert code == 0, out


# --- The minimum build size -------------------------------------------------

def test_a_four_page_build_is_too_few_to_be_real(tmp_path, capsys, monkeypatch):
    """lfr-tunnel's own NO-SCAN threshold was 5 pages (#141): a near-empty build passes every
    assertion, so it must not be reported as a pass."""
    import check_docs_rendered
    site = _write_site(tmp_path, home=PLAIN_HOME)
    (site / 'guides' / 'index.html').unlink(missing_ok=True)
    assert len(list(site.rglob('*.html'))) == 4

    code, out = _run_check(site, {'site_name': 'demo'}, capsys)
    assert code == 1 and 'NO-SCAN' in out, out

    # The control: the same four pages pass every other check, so NO-SCAN is the only failure.
    monkeypatch.setattr(check_docs_rendered, 'MIN_PAGES', 4)
    code, out = _run_check(site, {'site_name': 'demo'}, capsys)
    assert code == 0, out
