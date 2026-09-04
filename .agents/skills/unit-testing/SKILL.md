---
name: unit-testing
description: >-
  Enforces test-driven development, empirical verification gates, non-interactive test runs, and test suite integrity.
  Load when writing tests, refactoring, or investigating test failures.
---

# Skill: Unit Testing & Verification Hard-Gates

---

## Directives & Rules of Engagement

### 1. Test-Driven Alignment
Before executing implementation logic for new features or bug fixes, the agent MUST propose test cases (unit, integration, or table-driven tests) and confirm test coverage requirements.

### 2. Empirical Verification Gate
The agent is FORBIDDEN from declaring a task resolved or a bug fixed based on file edits alone. The corresponding test suite command MUST be executed, and clean passing output MUST be verified.

### 3. Non-Interactive Test Execution
Test commands MUST be run in non-interactive mode:
- **Python**: `pytest -v --tb=short`
- **Go**: see the warning below -- never bare `go test`/`go test ./...`.
- **Rust**: `cargo test --quiet`
- **Java**: `mvn test -B` or `./gradlew test --no-daemon`
- **Node.js**: `npm test -- --ci` or `npx vitest run`

> [!WARNING]
> **Go: never run bare `go test` or `go test ./...`.** It compiles an unsigned
> test binary into the OS's default temp directory and executes it from
> there. For any package under test that opens a real network listener
> (`httptest.Server`, a WebSocket server, anything binding a socket -- common
> in server-side Go test suites), this is exactly the pattern behavior-based
> endpoint security tools (SentinelOne, CrowdStrike, etc.) flag as a
> dropped-and-executed malicious binary. This is not theoretical: a project
> built from this template had a test binary flagged as "Malicious file
> executed," and the EDR response terminated the session and deleted
> unrelated local tooling as collateral damage.
>
> Instead, build each package's test binary explicitly into a directory the
> project controls (and can get EDR-allowlisted if needed), then run that
> binary directly:
>
> ```bash
> mkdir -p .test-bin
> for pkg in $(go list -f '{{if .TestGoFiles}}{{.ImportPath}}{{end}}' ./...); do
>   go test -c -o .test-bin/pkg.test "$pkg" || exit 1
>   (cd "$(go list -f '{{.Dir}}' "$pkg")" && "$OLDPWD/.test-bin/pkg.test") || exit 1
> done
> ```
>
> Wrap this in a `Makefile` target (e.g. `make test`) or a script once the
> project has one, rather than typing it out each time.

### 4. No Superficial Test Fixes
Never fix failing tests by commenting out assertions, reducing test thresholds, or deleting test cases. If a test fails, identify why the underlying implementation contract was broken and repair the core logic.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-04* | *Last Reviewed: 2026-09-04*
