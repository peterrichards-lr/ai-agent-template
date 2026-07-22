# Skill: Reflection & Planning

**Trigger Condition**: Load this skill when beginning complex tasks, multi-file refactoring, introducing new architectural components, or when requested to plan.

---

## Directives & Rules of Engagement

### 1. Mandatory Implementation Planning
Before making multi-file edits or implementing logic blocks larger than 10 lines, the agent MUST output an implementation plan using the `implementation_plan.md` artifact format:

- **Goal Description**: Clear summary of what the change accomplishes.
- **User Review Required**: Highlight breaking changes, architectural choices, or design trade-offs.
- **Open Questions**: Explicitly state design ambiguities requiring human input.
- **Proposed Changes**: List exact files to be modified, created, or deleted (`[MODIFY]`, `[NEW]`, `[DELETE]`).
- **Verification Plan**: Detail both automated test commands and manual verification steps.

### 2. User Approval Gate
The agent MUST set `request_feedback=true` on the implementation plan artifact and end its turn. File modification tools MUST NOT be called until the user explicitly responds with approval (e.g. "Proceed").

### 3. Predictive Failure Analysis
For non-trivial logic edits, the agent MUST append a section titled **Failure Analysis** to its task summary detailing:
1. **Edge Case 1**: Description of potential edge case / error boundary & how the code handles it.
2. **Edge Case 2**: Description of concurrency, memory, or network failure & how the code handles it.

### 4. Atomic Work Units
Break multi-step implementations into discrete, isolated steps. Execute Step 1, verify tool output, summarize findings, and halt for user feedback before proceeding to Step 2.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-07-22* | *Last Reviewed: 2026-07-22*
