# Reference

**Information-oriented.** Reference material describes the machinery: every
command, flag, environment variable, configuration key, exit code and schema
field. It is consulted, not read. Accuracy and completeness beat readability.

## What belongs here

- CLI command and flag tables.
- Configuration file keys, with types, defaults and valid ranges.
- Exit codes, error codes, wire formats, schemas.
- Compatibility and support matrices.

## What does not

| If the page... | It belongs in |
| --- | --- |
| Walks someone through their first success | [`docs/tutorials/`](../tutorials/index.md) |
| Solves a specific task | [`docs/how-to/`](../how-to/index.md) |
| Justifies a trade-off | [`docs/explanation/`](../explanation/index.md) |

## Writing rules

- Structure mirrors the code. If the CLI has three command groups, so does this
  section.
- Describe, do not instruct. Reference says what a flag *is*; a how-to says when
  to reach for it.
- Prefer tables to prose, and keep the ordering stable so diffs stay readable.
- This is the section most likely to go stale silently, which is exactly what the
  `*Last Reviewed*` footer and `scripts/check_docs_review.py` exist to catch.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
