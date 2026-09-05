# How-To Guides

**Task-oriented.** A how-to guide answers "how do I ...?" for a reader who
already knows what they want and needs the shortest correct route there. It may
assume competence; a tutorial may not.

## What belongs here

- [Publish this documentation site](publish-the-documentation-site.md)
- [Protect the main branch](../BRANCH_PROTECTION.md)

Add a guide per real task. Title it with the task, starting with a verb —
"Rotate the signing key", not "Signing keys".

## What does not

| If the page... | It belongs in |
| --- | --- |
| Teaches a newcomer from zero | [`docs/tutorials/`](../tutorials/index.md) |
| Lists every option of a command | [`docs/reference/`](../reference/index.md) |
| Explains why the design is the way it is | [`docs/explanation/`](../explanation/index.md) |

## Writing rules

- One page, one task. If the title needs "and", split it.
- State the preconditions up front, then the steps, then how to verify success.
- Link to reference material for the exhaustive option lists; do not restate them
  here, because the copy will rot.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
