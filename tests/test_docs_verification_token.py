"""
test_docs_verification_token.py - A site can require a specific verification token

ai-agent-template#161: a required MISSING-VERIFICATION was satisfied by either token, so a site
that depends on Search Console could swap Google's token for Bing's and pass, with no Google
tag on any page. lfr-tunnel reproduced it on its real build at v2.4.0 (comment on #155), and
lost its Search Console verification to a deleted key once before (lfr-tunnel#2381).

`required` and `waive` now accept MISSING-VERIFICATION:google and MISSING-VERIFICATION:bing,
and the Liferay profile requires Google's. Plain MISSING-VERIFICATION still means either token.

A dedicated module beside tests/test_docs_required_profile.py, whose helpers it reuses.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from check_docs_rendered import check_required  # noqa: E402
from test_docs_required_profile import _delete, _met  # noqa: E402

GOOGLE = 'extra.google_site_verification'


def _generic(required=None, waive=None, **tokens):
    standard = {}
    if required is not None:
        standard['required'] = required
    if waive is not None:
        standard['waive'] = waive
    return {'site_name': 'demo', 'extra': {**tokens, 'docs_standard': standard}}


def _bing_instead_of_google():
    config = _delete(_met(), GOOGLE)
    config['extra']['bing_site_verification'] = 'BING'
    return config


def test_the_profile_fails_bing_in_place_of_google():
    """lfr-tunnel's case 1 on #155: v2.4.0 passed it."""
    problems = check_required(_bing_instead_of_google(), set())
    assert 'MISSING-VERIFICATION' not in problems, "either token still satisfies the plain check"
    assert any(f'{GOOGLE} is not set' in line
               for line in problems['MISSING-VERIFICATION:google']), problems
    assert any('required by the Liferay profile' in line
               for line in problems['MISSING-VERIFICATION:google'])


def test_the_profile_passes_with_google_and_bing():
    config = _met()
    config['extra']['bing_site_verification'] = 'BING'
    assert check_required(config, set()) == {}


@pytest.mark.parametrize('qualified, present, missing', [
    ('MISSING-VERIFICATION:google', {'bing_site_verification': 'B'}, GOOGLE),
    ('MISSING-VERIFICATION:bing', {'google_site_verification': 'G'},
     'extra.bing_site_verification'),
])
def test_a_site_can_require_a_specific_token(qualified, present, missing):
    problems = check_required(_generic(required=[qualified], **present), set())
    assert any(f'{missing} is not set' in line for line in problems[qualified]), problems


@pytest.mark.parametrize('qualified, token', [
    ('MISSING-VERIFICATION:google', 'google_site_verification'),
    ('MISSING-VERIFICATION:bing', 'bing_site_verification'),
])
def test_a_required_token_that_is_set_passes(qualified, token):
    assert check_required(_generic(required=[qualified], **{token: 'T'}), set()) == {}


def test_plain_verification_still_means_either_token():
    """Unchanged for a site with no profile that names the plain check."""
    config = _generic(required=['MISSING-VERIFICATION'], bing_site_verification='B')
    assert check_required(config, set()) == {}


def test_waiving_the_check_waives_its_qualified_forms():
    """The profile ships one waive for MISSING-VERIFICATION; it covers :google too."""
    config = _delete(_met(), GOOGLE)
    config['extra']['docs_standard']['waive'] = {'MISSING-VERIFICATION': 'No token yet.'}
    assert check_required(config, set()) == {}


def test_waiving_only_google_keeps_either_token_required():
    """A profile site that does not use Search Console waives :google, and still needs one."""
    config = _bing_instead_of_google()
    config['extra']['docs_standard']['waive'] = {'MISSING-VERIFICATION:google': 'Bing only.'}
    assert check_required(config, set()) == {}
    _delete(config, 'extra.bing_site_verification')
    assert 'MISSING-VERIFICATION' in check_required(config, set())


def test_waiving_the_plain_check_covers_a_required_qualified_one():
    config = _generic(required=['MISSING-VERIFICATION:google'],
                      waive={'MISSING-VERIFICATION': 'Not indexed yet.'})
    assert check_required(config, set()) == {}


def test_a_waive_of_a_token_nothing_requires_fails():
    config = _generic(waive={'MISSING-VERIFICATION:bing': 'stale'})
    problems = check_required(config, set())
    assert any('nothing requires MISSING-VERIFICATION:bing' in line
               for line in problems['REQUIRED']), problems


def test_an_unknown_token_is_an_unknown_name():
    problems = check_required(_generic(required=['MISSING-VERIFICATION:yandex']), set())
    assert any('unknown check name' in line for line in problems['REQUIRED']), problems
