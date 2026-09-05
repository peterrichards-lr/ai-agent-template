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

### 2. Fail-First Verification Gate (TDD Empirical Evidence)
The agent is FORBIDDEN from declaring a bug fixed or a new behavior verified based on a test suite that passed immediately upon writing. Clean passing output alone is evidence that the code compiles and regressions did not occur; it is *not* evidence that the new assertion has the power to fail.

1. **Empirical Failure Evidence**:
   - **For Bug Fixes**: The agent MUST write the reproduction test first, execute the test suite, and **cite the exact failing assertion output** (terminal snippet showing the red failure) *before* writing or modifying production code.
   - **For New Features / Behaviors**: If writing the test prior to implementation is impractical, the agent MUST mutate or temporarily disable the new logic post-implementation to observe and **cite the expected test failure**, verifying the assertion is not vacuously true.
   - **For Refactoring**: When restructuring existing code without altering observable behavior, existing tests must remain continuously green throughout; the existing test suite serves as the invariant baseline. Fail-first verification is strictly scoped to new, modified, or repaired behaviors.
2. **Mutation Reversion & Clean Pass Gate**:
   - When using the mutate-to-confirm fallback, the agent MUST revert the intentional mutation immediately, re-run the test suite to verify it returns to clean green, and cite the passing output. Leaving an un-reverted mutation or broken code in the working tree is strictly forbidden.
3. **Durable Citation in Pull Request**:
   - The agent MUST document the observed red-to-green transition (including the cited failing assertion snippet and subsequent passing verification) in the PR description so reviewers can verify proof of failure without requiring access to local agent scratchpads.

### 3. Empirical Verification Gate
The agent is FORBIDDEN from declaring a task resolved or a bug fixed based on file edits alone. The stopping condition is **the appropriate verification for this change**, executed and its output verified -- not merely "the test suite passed".

- For changes unit tests can prove, that is the test suite command, run with clean passing output verified, subject to rule 2 above.
- For changes unit tests cannot prove -- UI and rendering, anything crossing a process or network boundary, CLI interaction, configuration and deployment -- a green suite is a precondition, not the proof. `e2e-verification/SKILL.md` governs what real-system evidence is required, and how to escalate to `human-in-the-loop/SKILL.md` when it cannot be automated.

Rule 2 and `e2e-verification/SKILL.md` are the two branches of the same question: rule 2 tightens what a passing test proves; the e2e skill covers changes where a passing test proves nothing about the system.

### 4. Non-Interactive Test Execution
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

### 5. No Superficial Test Fixes
Never fix failing tests by commenting out assertions, reducing test thresholds, or deleting test cases. If a test fails, identify why the underlying implementation contract was broken and repair the core logic.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
