#!/usr/bin/env python3
"""
check_closing_refs.py - Validate PR Closing References & Prevent Premature Issue Closure

Enforces that issue closing keywords (closes, fixes, resolves) followed by an issue reference
appear strictly within the designated '## Linked Issue' (or '## Linked Issues') section
in the PR body.

Flags any closing reference in the PR title or outside '## Linked Issue', preventing
GitHub's parser from prematurely closing issues due to ignored English negations
(e.g., 'does not close #123').
"""

import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# Regex matching GitHub closing keywords followed by an issue number or issue URL
# GitHub supported keywords: close, closes, closed, fix, fixes, fixed, resolve, resolves, resolved
CLOSING_REF_REGEX = re.compile(
    r'\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b\s*:?\s*(?:#(\d+)|https?://github\.com/[^/\s]+/[^/\s]+/issues/(\d+))',
    re.IGNORECASE
)

# Heading pattern for splitting markdown into level-2 sections
HEADING_REGEX = re.compile(r'(?m)^##\s+(.+)$')
LINKED_ISSUE_HEADING_REGEX = re.compile(r'^Linked\s+Issues?$', re.IGNORECASE)

def split_markdown_sections(text: str) -> List[Tuple[str, str]]:
    """Split markdown text into (heading, content) tuples based on '## ' headers."""
    sections: List[Tuple[str, str]] = []
    matches = list(HEADING_REGEX.finditer(text))

    if not matches:
        return [("", text)]

    # Content preceding the first '## ' heading
    if matches[0].start() > 0:
        sections.append(("", text[:matches[0].start()]))

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end]
        sections.append((heading, content))

    return sections

def validate_pr_closing_refs(
    title: str,
    body: str,
    allow_no_issue: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate PR title and body for closing references.

    Returns (is_valid, violations_list).
    """
    violations: List[str] = []

    # 1. Check PR title
    title_matches = CLOSING_REF_REGEX.findall(title)
    if title_matches:
        for match in title_matches:
            kw = match[0]
            num = match[1] or match[2]
            violations.append(
                f"Closing reference '{kw} #{num}' found in PR title. "
                "Closing keywords belong strictly inside the '## Linked Issue' section in the PR body."
            )

    # 2. Split body into sections and inspect
    sections = split_markdown_sections(body)
    linked_issue_sections: List[Tuple[str, str]] = []
    other_sections: List[Tuple[str, str]] = []

    for heading, content in sections:
        if LINKED_ISSUE_HEADING_REGEX.match(heading):
            linked_issue_sections.append((heading, content))
        else:
            other_sections.append((heading, content))

    # Check for stray closing references outside '## Linked Issue'
    for heading, content in other_sections:
        matches = CLOSING_REF_REGEX.findall(content)
        if matches:
            loc = f"section '## {heading}'" if heading else "body preamble"
            for match in matches:
                kw = match[0]
                num = match[1] or match[2]
                violations.append(
                    f"Stray closing reference '{kw} #{num}' found in {loc}.\n"
                    "  ⚠️ GitHub ignores English negation words and surrounding context (e.g. 'does not close #123',\n"
                    "     'not fixing #123', 'part of #123' will still close issue 123 upon merge!).\n"
                    "  👉 Remedy: Move intentional closing references into the '## Linked Issue' section.\n"
                    "     For non-closing references, use phrasing without closing keywords (e.g. 'part of #123',\n"
                    "     'see #123', 'related to #123', 'addresses #123', or plain '#123')."
                )

    # 3. Check '## Linked Issue' section
    if not linked_issue_sections:
        if not allow_no_issue:
            violations.append(
                "Missing '## Linked Issue' section in PR body.\n"
                "  Every PR should close a tracked GitHub issue per .agents/skills/github-workflow/SKILL.md.\n"
                "  If this change is genuinely too trivial to need one, add the 'no-issue-needed' label instead."
            )
    else:
        # Combine all Linked Issue sections if multiple
        combined_linked_content = "\n".join(content for _, content in linked_issue_sections)
        linked_matches = CLOSING_REF_REGEX.findall(combined_linked_content)

        if not linked_matches:
            if not allow_no_issue:
                if re.search(r'#<[^>]+>', combined_linked_content):
                    violations.append(
                        "The '## Linked Issue' section contains an unpopulated placeholder ('#<issue-number>').\n"
                        "  Replace with a real issue reference (e.g. 'Closes #123') or add 'no-issue-needed' label."
                    )
                else:
                    violations.append(
                        "The '## Linked Issue' section does not contain a valid closing reference (e.g. 'Closes #123').\n"
                        "  Every PR must close a tracked GitHub issue, or carry the 'no-issue-needed' label."
                    )

    return len(violations) == 0, violations

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate PR closing keywords to prevent premature issue closure on merge."
    )
    parser.add_argument("--title", type=str, default=None, help="PR title text")
    parser.add_argument("--body", type=str, default=None, help="PR body markdown text")
    parser.add_argument("--body-file", type=Path, default=None, help="Path to file containing PR body markdown")
    parser.add_argument("--allow-no-issue", action="store_true", help="Allow PR without closing issue (e.g. no-issue-needed label)")

    args = parser.parse_args()

    title = args.title if args.title is not None else ""
    if args.body_file and args.body_file.exists():
        body = args.body_file.read_text(encoding="utf-8")
    elif args.body is not None:
        body = args.body
    else:
        body = ""

    is_valid, violations = validate_pr_closing_refs(title, body, allow_no_issue=args.allow_no_issue)

    if not is_valid:
        print("❌ PR Closing Reference Check Failed:", file=sys.stderr)
        for v in violations:
            print(f"- {v}", file=sys.stderr)
        return 1

    print("✓ PR closing references verified: strictly positioned in '## Linked Issue'.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
