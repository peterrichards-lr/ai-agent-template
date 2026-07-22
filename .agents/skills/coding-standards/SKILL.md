# Skill: Language-Agnostic Coding Standards

**Trigger Condition**: Load this skill when writing, refactoring, or reviewing source code across any programming language (Go, Python, Rust, Java, TypeScript, C++, etc.).

---

## Directives & Rules of Engagement

### 1. DRY Enforcement & Code Discovery
Before implementing new helper functions, utility methods, or data classes, the agent MUST run search tools (`grep_search`) across the codebase to look for pre-existing utilities. Tool search results MUST be cited in the response to prove verification.

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

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
