"""
test_docs_required_profile.py - Required checks cannot be weakened by deleting a key

ai-agent-template#155, measured on lfr-tunnel's build at v2.3.1. `required` (#141) stopped a
deleted top-level key from switching a check off, but:

- a deleted sub-key left a required check running and checking less: notice.text and
  notice.link_text (NO-NOTICE), related.heading (HOME-LAYOUT, which then skipped the whole
  related section);
- `required` itself, or one name in it, could be deleted, turning that check back to opt-in;
- required MISSING-SOCIAL keyed only on social_image, so deleting extra.favicon_svg or
  theme.favicon skipped those parts.

Now a required check needs its sub-keys too, the Liferay profile requires its four checks by
default, and a site drops one only through a waive entry with a reason. Every deletion case in
#155 is a test below.

A dedicated module, so parallel docs-site work does not conflict on one file.
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from check_docs_rendered import check_required, profile_required  # noqa: E402
from test_docs_site import _liferay_config, _run_check, _write_site  # noqa: E402

PROFILE_CHECKS = ('NO-NOTICE', 'HOME-LAYOUT', 'MISSING-VERIFICATION', 'MISSING-SOCIAL')


def _met():
    """A Liferay profile site that meets all four required checks, with nothing waived."""
    config = copy.deepcopy(_liferay_config())
    config['extra'].update(google_site_verification='TOKEN', social_image='assets/s.png',
                           favicon_svg='assets/favicon.svg')
    config['extra']['docs_standard'].pop('waive', None)
    config['theme'] = {'favicon': 'assets/favicon.png'}
    return config


def _delete(config, dotted):
    *parents, leaf = dotted.split('.')
    node = config
    for key in parents:
        node = node[key]
    del node[leaf]
    return config


def test_the_met_site_needs_nothing():
    assert check_required(_met(), set()) == {}


def test_the_profile_is_known_by_its_stylesheet():
    assert profile_required(_met()) == ('the Liferay profile', PROFILE_CHECKS)
    assert profile_required({'extra_css': ['assets/stylesheets/site.css']}) == (None, ())


@pytest.mark.parametrize('dotted, check', [
    # The three #155 found passing silently...
    ('extra.docs_standard.notice.text', 'NO-NOTICE'),
    ('extra.docs_standard.notice.link_text', 'NO-NOTICE'),
    ('extra.docs_standard.related.heading', 'HOME-LAYOUT'),
    # ...and the three it found caught by an empty comparison, now named as missing.
    ('extra.docs_standard.notice.title', 'NO-NOTICE'),
    ('extra.docs_standard.related.intro', 'HOME-LAYOUT'),
    ('extra.docs_standard.related.rows', 'HOME-LAYOUT'),
    # Top-level keys, as in #141.
    ('extra.docs_standard.notice', 'NO-NOTICE'),
    ('extra.docs_standard.home_layout', 'HOME-LAYOUT'),
    ('extra.google_site_verification', 'MISSING-VERIFICATION'),
    ('extra.social_image', 'MISSING-SOCIAL'),
    # (c): the icons are part of a required MISSING-SOCIAL.
    ('extra.favicon_svg', 'MISSING-SOCIAL'),
    ('theme.favicon', 'MISSING-SOCIAL'),
])
def test_deleting_a_key_a_required_check_needs_fails_and_names_it(dotted, check):
    problems = check_required(_delete(_met(), dotted), set())
    assert check in problems, f"deleting {dotted} passed: {problems}"
    key = dotted if dotted != 'extra.docs_standard.notice' else 'extra.docs_standard.notice.title'
    assert any(key in line for line in problems[check]), problems[check]


def test_a_site_with_no_related_block_needs_no_related_keys():
    """'HOME-LAYOUT with a related block': a site with no related projects has no section."""
    assert check_required(_delete(_met(), 'extra.docs_standard.related'), set()) == {}


def test_deleting_required_does_not_turn_a_profile_check_off():
    """#155 follow-up 1: the profile's default holds when `required` is deleted outright."""
    config = _met()
    config['extra']['docs_standard']['required'] = list(PROFILE_CHECKS)
    del config['extra']['docs_standard']['required']
    _delete(config, 'extra.google_site_verification')
    assert 'MISSING-VERIFICATION' in check_required(config, set())


def test_removing_one_name_from_required_does_not_turn_it_off():
    config = _met()
    config['extra']['docs_standard']['required'] = ['NO-NOTICE', 'HOME-LAYOUT',
                                                    'MISSING-SOCIAL']   # VERIFICATION removed
    _delete(config, 'extra.google_site_verification')
    assert 'MISSING-VERIFICATION' in check_required(config, set())


def test_a_waive_with_a_reason_drops_a_profile_check():
    config = _delete(_met(), 'extra.google_site_verification')
    config['extra']['docs_standard']['waive'] = {'MISSING-VERIFICATION': 'Not indexed yet.'}
    assert check_required(config, set()) == {}


@pytest.mark.parametrize('reason', ['', '   ', None])
def test_a_waive_without_a_reason_fails_and_waives_nothing(reason):
    config = _delete(_met(), 'extra.google_site_verification')
    config['extra']['docs_standard']['waive'] = {'MISSING-VERIFICATION': reason}
    problems = check_required(config, set())
    assert any('gives no reason' in line for line in problems['REQUIRED']), problems
    assert 'MISSING-VERIFICATION' in problems, "an unexplained waive must not waive"


def test_a_waive_of_an_unknown_name_fails():
    config = _met()
    config['extra']['docs_standard']['waive'] = {'MISSING-SOCAIL': 'typo'}
    assert any('unknown check name' in line for line in check_required(config, set())['REQUIRED'])


def test_a_waive_of_a_check_nothing_requires_fails():
    """A generic site has no profile defaults: a stale or copied waive is named."""
    config = {'site_name': 'demo',
              'extra': {'docs_standard': {'waive': {'HOME-LAYOUT': 'not written'}}}}
    problems = check_required(config, set())
    assert any('nothing requires HOME-LAYOUT' in line for line in problems['REQUIRED'])


def test_waive_must_be_a_mapping():
    config = _met()
    config['extra']['docs_standard']['waive'] = ['MISSING-SOCIAL']
    assert any('must map a check name' in line
               for line in check_required(config, set())['REQUIRED'])


def test_a_generic_site_still_requires_nothing_by_default(tmp_path, capsys):
    """Unchanged for a site with no profile: an unconfigured check is skipped."""
    site = _write_site(tmp_path, home='<h1>demo</h1><p>Hello.</p>')
    code, out = _run_check(site, {'site_name': 'demo'}, capsys)
    assert code == 0, out


def test_the_shipped_profile_waives_all_four_with_reasons():
    waive = _liferay_fresh()['extra']['docs_standard']['waive']
    assert sorted(waive) == sorted(PROFILE_CHECKS)
    assert all(isinstance(r, str) and r.strip() for r in waive.values())


def test_a_fresh_profile_site_passes_and_deleting_its_waives_fails_it(tmp_path, capsys):
    """Deleting a waive only ever turns a check on."""
    site = _write_site(tmp_path, home='<h1>Liferay Tunnel</h1><p>New.</p>')
    fresh = _liferay_fresh()
    code, out = _run_check(site, fresh, capsys)
    assert code == 0, out
    del fresh['extra']['docs_standard']['waive']
    code, out = _run_check(site, fresh, capsys)
    assert code == 1
    for name in PROFILE_CHECKS:
        assert f'[{name}]' in out, f"{name} is required once the waive is gone\n{out}"


def test_a_waived_check_that_is_configured_still_runs(tmp_path, capsys):
    """A waive drops the requirement, not the check: a configured notice is still held to."""
    config = _liferay_config()
    config['extra']['docs_standard']['waive'] = {'NO-NOTICE': 'testing'}
    site = _write_site(tmp_path, home='<h1>Liferay Tunnel documentation</h1><p>x</p>')
    code, out = _run_check(site, config, capsys)
    assert code == 1 and '[NO-NOTICE]' in out, out


def _liferay_fresh():
    """The profile as bootstrap writes it: home page not written, all four checks waived."""
    import yaml
    from test_docs_site import LIFERAY_PROFILE
    site = yaml.safe_load((LIFERAY_PROFILE / 'site.yml').read_text(encoding='utf-8')
                          .replace('<PROJECT_NAME_PLACEHOLDER>', 'Liferay Tunnel'))
    return {'site_name': 'lfr-tunnel', **site}
