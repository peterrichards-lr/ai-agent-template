"""
test_workflow_pinning.py - Supply-Chain Pinning Policy Enforcement

Mechanically enforces the template's GitHub Actions supply-chain policy rather
than leaving it as prose in SECURITY.md:

1. Every `uses:` in `.github/workflows/*.yml` references a full 40-character
   commit SHA, not a mutable tag (`@v7`) or branch (`@main`). A mutable tag can
   be silently repointed by the action owner or an attacker who compromises it,
   and the retagged code then runs with this repository's workflow token.
2. Every pinned `uses:` carries a trailing `# vX.Y.Z` comment so a human can
   read the version without resolving the SHA, and so Dependabot has the
   version marker it rewrites when it bumps the pin.
3. `.github/dependabot.yml` declares a `cooldown:` for every ecosystem, so a
   compromised release published minutes ago is not adopted immediately.

Commented-out `uses:` lines count. The CodeQL job stub at the foot of
`security-scan.yml` is documentation a downstream project uncomments verbatim;
shipping it with a mutable tag would reintroduce the finding on the first
uncomment.

Deliberately a dedicated module rather than an addition to
tests/test_template_scripts.py: the pinning policy spans every workflow file
and evolves with the supply-chain posture, not with the template automation
scripts. pytest auto-discovers tests/test_*.py.
"""

import re
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).parent.parent
WORKFLOWS_DIR = ROOT_DIR / '.github' / 'workflows'
DEPENDABOT_CONFIG = ROOT_DIR / '.github' / 'dependabot.yml'
SECURITY_POLICY = ROOT_DIR / 'SECURITY.md'

# Matches a `uses:` step reference whether or not the line is commented out,
# capturing the action reference and whatever trails it on the same line.
USES_LINE_PATTERN = re.compile(
    r'^\s*(?:#\s*)?(?:-\s*)?uses:\s*(?P<reference>\S+)(?P<trailer>.*)$'
)

# owner/repo[/path]@<40 lowercase hex characters>
SHA_PINNED_PATTERN = re.compile(r'^[\w.\-]+/[\w.\-/]+@[0-9a-f]{40}$')

# A trailing `# v1.2.3` (or `# v1`) comment naming the pinned release.
VERSION_COMMENT_PATTERN = re.compile(r'^\s*#\s*v\d+(?:\.\d+)*\S*\s*$')

# Local composite actions (`./.github/actions/foo`) live in this repository and
# are already pinned by the commit under test, so they need no SHA.
LOCAL_ACTION_PREFIX = './'


def workflow_files() -> list[Path]:
    files = sorted(WORKFLOWS_DIR.glob('*.yml')) + sorted(WORKFLOWS_DIR.glob('*.yaml'))
    assert files, f"Expected at least one workflow file in {WORKFLOWS_DIR}"
    return files


def collect_uses_lines() -> list[tuple[Path, int, str, str]]:
    """Return (path, line number, reference, trailer) for every `uses:` line."""
    found = []
    for path in workflow_files():
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            match = USES_LINE_PATTERN.match(line)
            if match:
                found.append(
                    (path, line_number, match.group('reference'), match.group('trailer'))
                )
    return found


def load_workflow(path: Path) -> dict:
    """Parse a workflow file, tolerating YAML 1.1 coercion of the `on:` key to True."""
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if True in data and 'on' not in data:
        data['on'] = data.pop(True)
    return data


def test_every_workflow_uses_reference_is_sha_pinned():
    """No `uses:` may reference a mutable tag or branch."""
    uses_lines = collect_uses_lines()
    assert uses_lines, "Expected to find `uses:` references in .github/workflows"

    unpinned = [
        f"{path.name}:{line_number}: {reference}"
        for path, line_number, reference, _ in uses_lines
        if not reference.startswith(LOCAL_ACTION_PREFIX)
        and not SHA_PINNED_PATTERN.match(reference)
    ]

    assert not unpinned, (
        "Every `uses:` must be pinned to a full 40-character commit SHA "
        "(mutable tags can be silently repointed). Unpinned references:\n  "
        + "\n  ".join(unpinned)
    )


def test_every_pinned_uses_reference_carries_a_version_comment():
    """A bare SHA is unreadable; the release it corresponds to must be named."""
    uses_lines = collect_uses_lines()

    missing_comment = [
        f"{path.name}:{line_number}: {reference}{trailer}"
        for path, line_number, reference, trailer in uses_lines
        if not reference.startswith(LOCAL_ACTION_PREFIX)
        and not VERSION_COMMENT_PATTERN.match(trailer)
    ]

    assert not missing_comment, (
        "Every SHA-pinned `uses:` must carry a trailing `# vX.Y.Z` comment naming "
        "the release, so reviewers can read the version and Dependabot can rewrite "
        "it on bump. References missing the comment:\n  "
        + "\n  ".join(missing_comment)
    )


def test_commented_codeql_stub_is_pinned_like_live_steps():
    """The uncomment-to-enable CodeQL stub must not ship a mutable tag."""
    security_workflow = WORKFLOWS_DIR / 'security-scan.yml'
    assert security_workflow.exists(), "Expected .github/workflows/security-scan.yml to exist"

    commented_uses = [
        reference
        for path, _, reference, _ in collect_uses_lines()
        if path == security_workflow and 'codeql-action' in reference
    ]

    assert commented_uses, "Expected the CodeQL stub to reference github/codeql-action"
    for reference in commented_uses:
        assert SHA_PINNED_PATTERN.match(reference), (
            f"CodeQL stub reference '{reference}' is not SHA-pinned; a downstream "
            "project uncommenting it verbatim would reintroduce a mutable tag"
        )


def test_dependabot_declares_a_cooldown_for_every_ecosystem():
    """A cooldown delays adoption of a freshly published (possibly compromised) release."""
    assert DEPENDABOT_CONFIG.exists(), "Expected .github/dependabot.yml to exist"

    config = yaml.safe_load(DEPENDABOT_CONFIG.read_text(encoding='utf-8')) or {}
    updates = config.get('updates', [])
    assert updates, "Expected .github/dependabot.yml to declare update entries"

    for entry in updates:
        ecosystem = entry.get('package-ecosystem', '<unknown>')
        cooldown = entry.get('cooldown')
        assert isinstance(cooldown, dict) and cooldown, (
            f"Dependabot ecosystem '{ecosystem}' declares no `cooldown:`; a release "
            "published minutes ago would be adopted immediately"
        )
        assert any(
            isinstance(value, int) and value > 0
            for key, value in cooldown.items()
            if key.startswith('default-days') or key.endswith('-days')
        ), f"Dependabot ecosystem '{ecosystem}' has a `cooldown:` with no positive day count"


def test_security_policy_documents_the_pinning_rules():
    """The policy must be written down, including why pinning does not freeze updates."""
    policy = SECURITY_POLICY.read_text(encoding='utf-8')

    assert "Action Pinning & Update Cooldown" in policy, (
        "Expected SECURITY.md to document the SHA-pinning policy"
    )
    assert "dependabot" in policy.lower(), (
        "Expected SECURITY.md to explain that Dependabot still bumps SHA pins"
    )
    assert "cooldown" in policy.lower(), (
        "Expected SECURITY.md to document the Dependabot cooldown"
    )
