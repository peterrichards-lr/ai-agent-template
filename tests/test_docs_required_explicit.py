"""
test_docs_required_explicit.py - An explicitly required check holds what the profile's does

ai-agent-template#175: PROFILE_KEYS (what a profile requires of a check beyond its own keys)
applied only when the profile itself required the check. lfr-tunnel listed HOME-LAYOUT in
`required`, swapped the extra_css entry for another stylesheet so the profile was not
recognised, and deleted the `related` block: exit 0, HOME-LAYOUT passing (review of
peterrichards-lr/lfr-tunnel#2414).

The rule is general, not a HOME-LAYOUT special case: a check's profile keys apply whenever the
check is required, by the profile or by the site's own `required` list, whether or not the
profile is recognised. The per-check tests below are generated from PROFILE_KEYS, so a check
given profile keys later is covered without a new test.

A dedicated module beside tests/test_docs_required_profile.py, whose helpers it reuses.
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from check_docs_rendered import (  # noqa: E402
    CONFIGURED_CHECKS, PROFILE_KEYS, check_required, profile_required, required_keys)
from test_docs_required_profile import _delete, _met  # noqa: E402
from test_docs_site import _liferay_config, _run_check, _write_site  # noqa: E402

PROFILE_KEY_CASES = [(label, check, key) for label, checks in PROFILE_KEYS.items()
                     for check, keys in checks.items() for key, _ in keys]


def _explicit(check):
    """A site with no recognised profile, meeting everything, that lists `check` itself."""
    config = _met()
    config['extra_css'] = ['assets/stylesheets/site.css']
    config['extra']['docs_standard']['required'] = [check]
    assert profile_required(config) == (None, ())
    return config


def test_there_are_profile_keys_to_test():
    assert PROFILE_KEY_CASES, "PROFILE_KEYS is empty: these tests would pass vacuously"


@pytest.mark.parametrize('label, check, key', PROFILE_KEY_CASES)
def test_an_explicitly_required_check_needs_its_profile_keys(label, check, key):
    """Deleting a profile key fails an explicitly required check, profile unrecognised."""
    problems = check_required(_delete(_explicit(check), key), set())
    assert any(f'{key} is not set' in line for line in problems.get(check, [])), problems
    assert any('by extra.docs_standard.required' in line for line in problems[check])


@pytest.mark.parametrize('label, check, key', PROFILE_KEY_CASES)
def test_an_explicitly_required_check_with_its_profile_keys_passes(label, check, key):
    assert check not in check_required(_explicit(check), set())


@pytest.mark.parametrize('label, check, key', PROFILE_KEY_CASES)
def test_a_waive_still_drops_an_explicitly_required_check(label, check, key):
    config = _delete(_explicit(check), key)
    config['extra']['docs_standard']['waive'] = {check: 'No related tools yet.'}
    assert check not in check_required(config, set())


@pytest.mark.parametrize('label, check, key', PROFILE_KEY_CASES)
def test_required_by_both_names_each_missing_key_once(label, check, key):
    """The profile and `required` both requiring it: one requirement, not two."""
    config = _delete(_met(), key)
    config['extra']['docs_standard']['required'] = [check]
    problems = check_required(config, set())[check]
    assert sum(f'{key} is not set' in line for line in problems) == 1, problems


def test_a_check_with_no_profile_keys_is_unchanged():
    """The control: only CONFIGURED_CHECKS for a check no profile adds keys to."""
    plain = [name for name in CONFIGURED_CHECKS
             if not any(name in checks for checks in PROFILE_KEYS.values())]
    assert plain
    for name in plain:
        assert required_keys(name, explicit=True) == CONFIGURED_CHECKS[name]


def test_lfr_tunnels_reproduction_fails(tmp_path, capsys):
    """#175 exactly, through the real check: another stylesheet in extra_css (and none with
    the profile marker in the build), the related block deleted, the four checks in
    `required`. v2.5.0 exited 0 with HOME-LAYOUT passing."""
    config = copy.deepcopy(_liferay_config())
    config['extra_css'] = ['assets/stylesheets/site.css']
    standard = config['extra']['docs_standard']
    standard['required'] = ['MISSING-VERIFICATION', 'MISSING-SOCIAL', 'NO-NOTICE', 'HOME-LAYOUT']
    del standard['related']
    site = _write_site(tmp_path)
    assert profile_required(config, site) == (None, ()), "the profile must not be recognised"
    code, out = _run_check(site, config, capsys)
    assert code == 1, out
    assert '[HOME-LAYOUT]' in out and 'extra.docs_standard.related is not set' in out, out
