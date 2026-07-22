# Skill: Documentation Hygiene & Timestamp Maintenance

**Trigger Condition**: Load this skill after completing any code change, feature implementation, refactoring, or documentation update.

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
1. Review existing project documentation (`README.md`, `GEMINI.md`, `architecture.md`, etc.).
2. Update relevant markdown content if the implementation changed usage patterns, interfaces, or setup steps.
3. Run `python3 scripts/append_timestamps.py` to ensure all markdown files have valid footers.
4. Run `python3 scripts/check_docs_review.py` to verify that no documents violate review staleness thresholds.

### 3. Missing Documentation Remediation
If a feature introduces new commands, CLI flags, configuration parameters, or architecture modules without corresponding documentation, create a new doc or section with valid timestamp footers.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
