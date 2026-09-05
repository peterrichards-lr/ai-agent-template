#!/usr/bin/env python3
"""
check_commit_attribution.py - Guard Against Unattributable Commit Authorship

GitHub rulesets (and org-level policies) can require an extra approving review for
"unattributed" changes -- commits whose author email GitHub cannot map to a verified
account. On a solo-maintainer repository that is a dead end: you cannot approve your
own pull request, an empty `bypass_actors` list removes the admin override, and the
only remaining exit is rewriting history and force-pushing.

This script runs *before* a commit exists (as a pre-commit hook), so the fix is a
one-line `git config` change rather than a history rewrite.

IMPORTANT: the check is a heuristic. It recognises GitHub `@users.noreply.github.com`
addresses and an explicit allowlist; it cannot see which addresses are verified on
your GitHub account. A verified custom-domain address attributes perfectly well and
will still fail this check -- which is what the allowlist is for.
"""

import argparse
import os
import re
import subprocess
import sys
from typing import Iterable, List, Mapping, Optional, Tuple

# Addresses issued by GitHub for a specific account; always attributable.
GITHUB_NOREPLY_DOMAIN = 'users.noreply.github.com'

# Multi-valued git config key holding addresses the maintainer has confirmed are
# verified on their GitHub account (read with `git config --get-all`).
ALLOWLIST_CONFIG_KEY = 'user.attributableEmails'

# Values git config uses to express boolean truth, reused for CI environment flags.
TRUTHY_ENVIRONMENT_VALUES = frozenset({'1', 'true', 'yes', 'on'})

# Environment variables set by CI runners. The guard protects local commit creation,
# so it stands down when no local git identity is being used to author anything.
CI_ENVIRONMENT_VARIABLES = ('CI', 'GITHUB_ACTIONS')

ALLOWLIST_SEPARATOR_REGEX = re.compile(r'[,\s]+')

MISSING_EMAIL_MESSAGE = (
    "git config user.email is not set, so commits would be authored anonymously and\n"
    "  GitHub could not attribute them to any account.\n\n"
    "  Set it before committing:\n"
    "    git config user.email \"<ID>+<username>@users.noreply.github.com\"\n\n"
    "  Your noreply address is shown at GitHub -> Settings -> Emails -> "
    "\"Keep my email addresses private\"."
)


def build_unattributable_message(email: str) -> str:
    """Explain the heuristic failure without asserting that the address is wrong."""
    return (
        f"'{email}' is not recognised as an attributable commit author address.\n\n"
        "  This check is a HEURISTIC, not a verdict on your email. It recognises only\n"
        f"  GitHub @{GITHUB_NOREPLY_DOMAIN} addresses and an explicit allowlist -- it\n"
        "  cannot see which addresses are verified on your GitHub account. If this address\n"
        "  is already verified there (a custom domain, for example), it attributes fine and\n"
        "  this check is simply wrong about it. Allowlist it and move on:\n\n"
        f"    git config --add {ALLOWLIST_CONFIG_KEY} \"{email}\"\n\n"
        "  Otherwise, switch to your GitHub-issued noreply address:\n\n"
        "    git config user.email \"<ID>+<username>@users.noreply.github.com\"\n\n"
        "  Why this matters: a repository ruleset or org policy may require an extra\n"
        "  approving review for unattributed changes. A solo maintainer cannot satisfy\n"
        "  that (no self-approval, and no bypass actor), so the only escape from an\n"
        "  already-pushed commit is rewriting history and force-pushing. Fixing the\n"
        "  address now, before the commit exists, avoids that entirely."
    )


def parse_allowlist_entries(raw_values: Optional[Iterable[str]]) -> List[str]:
    """Normalise raw git config / CLI allowlist values into lowercase addresses.

    Accepts several values (git config --get-all) each of which may itself hold a
    comma- or whitespace-separated list.
    """
    if not raw_values:
        return []

    entries: List[str] = []
    for raw_value in raw_values:
        if not raw_value:
            continue
        for candidate in ALLOWLIST_SEPARATOR_REGEX.split(raw_value.strip()):
            normalised = candidate.strip().lower()
            if normalised:
                entries.append(normalised)
    return entries


def read_git_config_values(key: str, get_all: bool = False) -> List[str]:
    """Return git config values for a key, or an empty list when unset/unavailable."""
    command = ['git', 'config', '--get-all', key] if get_all else ['git', 'config', key]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except (OSError, FileNotFoundError):
        # git is not installed or not on PATH; the caller decides how to report this.
        return []

    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def is_continuous_integration_environment(environment: Mapping[str, str]) -> bool:
    """Detect a CI runner, where there is no local author identity worth guarding."""
    return any(
        str(environment.get(name, '')).strip().lower() in TRUTHY_ENVIRONMENT_VALUES
        for name in CI_ENVIRONMENT_VARIABLES
    )


def validate_commit_attribution(email: Optional[str], allowlist: Optional[Iterable[str]] = None) -> Tuple[bool, str]:
    """Check whether an author email is plausibly attributable to a GitHub account.

    Returns (is_attributable, message). The message is remediation guidance on
    failure and a short confirmation on success.
    """
    normalised_email = (email or '').strip().lower()
    if not normalised_email:
        return False, MISSING_EMAIL_MESSAGE

    if normalised_email.endswith('@' + GITHUB_NOREPLY_DOMAIN):
        return True, f"'{normalised_email}' is a GitHub noreply address; commits attribute automatically."

    allowlist_entries = parse_allowlist_entries(allowlist)
    if normalised_email in allowlist_entries:
        return True, f"'{normalised_email}' is allowlisted via {ALLOWLIST_CONFIG_KEY}."

    return False, build_unattributable_message(normalised_email)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Verify git author email is plausibly attributable to a GitHub account.'
    )
    parser.add_argument(
        '--email',
        help='Author email to check. Defaults to `git config user.email`. '
             'Passing this explicitly also disables the CI stand-down.'
    )
    parser.add_argument(
        '--allowlist',
        action='append',
        help=f'Additional attributable address(es). Merged with `git config --get-all {ALLOWLIST_CONFIG_KEY}` '
             'unless --email is given. May be repeated or comma-separated.'
    )
    args = parser.parse_args()

    is_explicit_check = args.email is not None
    if not is_explicit_check and is_continuous_integration_environment(os.environ):
        print('✓ Commit attribution check skipped: CI environment (no local author identity to guard).')
        return 0

    if is_explicit_check:
        allowlist_values = list(args.allowlist or [])
        email = args.email
    else:
        allowlist_values = list(args.allowlist or []) + read_git_config_values(ALLOWLIST_CONFIG_KEY, get_all=True)
        configured_emails = read_git_config_values('user.email')
        email = configured_emails[0] if configured_emails else ''

    is_attributable, message = validate_commit_attribution(email, allowlist_values)
    if not is_attributable:
        print(f'❌ Commit attribution check failed: {message}', file=sys.stderr)
        return 1

    print(f'✓ Commit attribution check passed: {message}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
