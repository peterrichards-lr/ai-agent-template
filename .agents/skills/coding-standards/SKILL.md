---
name: coding-standards
description: >-
  Enforces DRY code discovery, self-documenting identifiers, predictive failure analysis, and safety guards.
  Load when writing, refactoring, or reviewing code in any programming language.
---

# Skill: Language-Agnostic Coding Standards

---

## Directives & Rules of Engagement

### 1. DRY Enforcement & Code Discovery
Before implementing new helper functions, utility methods, or data classes, the agent MUST use whatever code-search tool it has available (a grep/ripgrep-style search, an IDE symbol search, etc. -- the specific tool name varies by agent) to look across the codebase for pre-existing utilities. Tool search results MUST be cited in the response to prove verification.

### 2. Self-Documenting Code & Identifier Precision
- Use domain-accurate, explicit variable and function names.
- Preserve existing comments and docstrings unless explicitly asked to modify them.
- Avoid dynamic type coercion or hidden implicit conversions where static typing is available.

### 3. Defensive Safety Guards & Exception Handling
- **No Masking Exceptions**: Never swallow exceptions or errors with empty `catch` / `except:` blocks or returning silent `null` fallbacks.
- **Trace Back to Source**: If an API returns missing or invalid data, trace upstream providers instead of masking symptoms downstream.
- **Resource Cleanup**: Ensure files, database connections, and network sockets are safely closed using language idiomatic resource management (`defer`, `with`, `RAII`, `try-with-resources`).

### 4. Language Idiom Alignment
- **Go**: Explicit error returns (`if err != nil`), `gofmt`, interface segregation, context propagation.
- **Python**: Type annotations (`typing`), `ruff` formatting, explicit exception hierarchy.
- **Rust**: Pattern matching, explicit `Result`/`Option` unwrapping without unsafe `unwrap()`, `clippy` compliance.
- **Java**: Dependency injection, strict type boundaries, stream immutability, `Checkstyle` adherence.
- **TypeScript/Node**: Immutable state, strict null checks (`tsconfig`), async/await over raw promises.

### 5. Mechanically Enforced Rules
- **Prose Is Advisory, a Pattern Is Enforced**: When you write a rule that a pattern-matcher could check, add a Semgrep rule for it in `.semgrep.yaml` rather than only prose in a skill file. Prose can be read and still violated; a rule in `.semgrep.yaml` is checked on every push and pull request by `.github/workflows/security-scan.yml` -- the same argument [`docs/BRANCH_PROTECTION.md`](../../../docs/BRANCH_PROTECTION.md) makes for rulesets over convention.
- **Cite the Prose in the Message**: A Semgrep rule's `message` MUST say what to use instead and cite the skill rule it mechanises, so the finding teaches the standard rather than merely blocking.
- **Non-Blocking by Default**: The scan runs `continue-on-error: true` and is not a required status check, so a new rule reports before it gates. Promote it to blocking only once existing findings are triaged to zero.

### 6. Scope Sprawl & Anti-Churn Guardrails
- **Focused Bugfixes**: Bugfix pull requests (branch starting with `fix/`, `fix-`, `bugfix/`, or `bugfix-`, or PR title starting with `fix:`/`bugfix:`/`bug:`) MUST be tightly focused on resolving the targeted defect and MUST NOT modify more than 10 files.
- **No Drive-by Refactoring**: Do not combine speculative refactoring, formatting cleanup, or codebase-wide renames into a bugfix. If unrelated improvements or tech debt are identified during an edit, log them as a separate issue (labeled `tech-debt`) rather than bloating the immediate fix.
- **Bypass Overrides**: If a legitimate defect repair fundamentally spans more than 10 files, an explicit bypass must be granted by a maintainer applying the `bypass-sprawl` PR label.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
