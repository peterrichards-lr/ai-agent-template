---
name: documentation
description: >-
  Governs documentation hygiene, timestamp maintenance (*Last Updated* | *Last Reviewed*), and staleness checks.
  Load after completing any code change, feature implementation, refactoring, or doc update.
---

# Skill: Documentation Hygiene & Timestamp Maintenance

---

## Directives & Rules of Engagement

### 1. Mandatory Markdown Footer Block
Every `.md` document created or modified in this repository MUST conclude with the following footer:

```markdown
<!-- markdownlint-disable MD049 -->
---
*Last Updated: YYYY-MM-DD* | *Last Reviewed: YYYY-MM-DD*
```

### 2. Post-Implementation Doc Verification
After completing a feature or bug fix:
1. Review existing project documentation (`README.md`, `AGENTS.md`, `docs/`, `architecture.md`, etc.).
2. Update relevant markdown content if the implementation changed usage patterns, interfaces, or setup steps.
3. Run `python3 scripts/append_timestamps.py` to ensure all markdown files have valid footers.
4. Run `python3 scripts/check_docs_review.py` to verify that no documents violate review staleness thresholds.

### 3. Missing Documentation Remediation
If a feature introduces new commands, CLI flags, configuration parameters, or architecture modules without corresponding documentation, create a new doc or section with valid timestamp footers.

### 4. Where a New Document Belongs (Diátaxis)
`docs/` is organised on the [Diátaxis](https://diataxis.fr) model. Deciding the division is the FIRST step of writing a page, not an afterthought — a correct page filed in the wrong division is unfindable. Answer two questions, in order:

1. **Does the reader already have a goal?** No → `docs/tutorials/`. Yes → `docs/how-to/`.
2. **Is the page consulted or read?** Consulted → `docs/reference/`. Read → `docs/explanation/`.

| Division | Purpose | The page reads like | Typical title |
| --- | --- | --- | --- |
| `docs/tutorials/` | Teach a newcomer to a first working result | A guided lesson, one route only | "Your first deployment" |
| `docs/how-to/` | Solve one task for someone who already knows what they want | A recipe: preconditions, steps, verification | "Rotate the signing key" |
| `docs/reference/` | Describe the machinery exhaustively and accurately | Tables of flags, keys, exit codes, schemas | "CLI reference" |
| `docs/explanation/` | Justify decisions and give background | An essay, read away from the keyboard | "Why the queue is single-writer" |

Rules of engagement:

- **Never mix divisions in one page.** A page that resists classification is two pages — split it and cross-link. Instructions inside an architecture essay, or an option table inside a tutorial, are the two most common failures.
- **Do not restate reference material** inside a how-to guide; link to it, because the copy will rot while the original is maintained.
- Nested directories are supported (`docs/how-to/deployment/blue-green.md`); `append_timestamps.py` and `check_docs_review.py` traverse the whole tree.
- Add the new page to `nav:` in `mkdocs.yml` when the repository has the optional documentation site enabled (`bootstrap_template.py --docs-site`). A page absent from `nav` is not published.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-04* | *Last Reviewed: 2026-09-04*
