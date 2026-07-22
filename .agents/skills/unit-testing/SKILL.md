# Skill: Unit Testing & Verification Hard-Gates

**Trigger Condition**: Load this skill when writing test cases, running test suites, refactoring code, or debugging test failures.

---

## Directives & Rules of Engagement

### 1. Test-Driven Alignment
Before executing implementation logic for new features or bug fixes, the agent MUST propose test cases (unit, integration, or table-driven tests) and confirm test coverage requirements.

### 2. Empirical Verification Gate
The agent is FORBIDDEN from declaring a task resolved or a bug fixed based on file edits alone. The corresponding test suite command MUST be executed, and clean passing output MUST be verified.

### 3. Non-Interactive Test Execution
Test commands MUST be run in non-interactive mode:
- **Python**: `pytest -v --tb=short`
- **Go**: `go test -v -race ./...`
- **Rust**: `cargo test --quiet`
- **Java**: `mvn test -B` or `./gradlew test --no-daemon`
- **Node.js**: `npm test -- --ci` or `npx vitest run`

### 4. No Superficial Test Fixes
Never fix failing tests by commenting out assertions, reducing test thresholds, or deleting test cases. If a test fails, identify why the underlying implementation contract was broken and repair the core logic.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
