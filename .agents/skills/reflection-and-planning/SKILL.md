# Skill: Reflection & Planning

**Trigger Condition**: Load this skill when beginning complex tasks, multi-file refactoring, introducing new architectural components, or when requested to plan.

---

## Directives & Rules of Engagement

### 1. Mandatory Implementation Planning
Before making multi-file edits or implementing logic blocks larger than 10 lines, the agent MUST write out an implementation plan covering:

- **Goal Description**: Clear summary of what the change accomplishes.
- **User Review Required**: Highlight breaking changes, architectural choices, or design trade-offs.
- **Open Questions**: Explicitly state design ambiguities requiring human input.
- **Proposed Changes**: List exact files to be modified, created, or deleted (`[MODIFY]`, `[NEW]`, `[DELETE]`).
- **Verification Plan**: Detail both automated test commands and manual verification steps.

Use whatever structured planning mechanism your agent provides for this (a dedicated plan-mode, a plan artifact, or simply a clearly formatted response) -- the content above is what's required, not a specific tool-call shape.

### 2. User Approval Gate
The agent MUST present the plan and then stop and wait for explicit human approval (e.g. "Proceed") before calling any file-modification tool. Use your agent's own mechanism for pausing and requesting feedback -- an explicit approval-request tool if one exists, or simply asking the question and ending the turn if it doesn't. Do not proceed to file edits on an assumption that silence or a vague acknowledgement counts as approval.

### 3. Issue Comment Sync & Open-Question Resolution
- **A plan with unresolved Open Questions is not actionable.** Do not begin implementation until every open question from the plan has been explicitly answered -- an unanswered design ambiguity is exactly the kind of thing that turns into a wrong implementation.
- If the work being planned is tied to a GitHub issue (see `github-workflow/SKILL.md`), once the plan is approved (Rule 2), post a concise summary of it -- goal, key file changes, open questions if any; not the full verbatim plan -- as a comment on that issue (`gh issue comment <issue-number> --body "..."`) before beginning implementation.
- When an open question is subsequently answered, post the answer as a further comment on the same issue.
- If answering an open question changes the plan, post the revised plan as another comment, clearly marked as a revision (e.g. "Revised plan (supersedes the above):") -- don't silently implement a different plan than the one the issue shows was approved.

This keeps the issue itself a complete, readable record of what was planned, questioned, resolved, and (if changed) revised -- independent of the agent's chat session, visible to a teammate, a future agent picking up the same issue, or anyone auditing the work later.

### 4. Predictive Failure Analysis
For non-trivial logic edits, the agent MUST append a section titled **Failure Analysis** to its task summary detailing:
1. **Edge Case 1**: Description of potential edge case / error boundary & how the code handles it.
2. **Edge Case 2**: Description of concurrency, memory, or network failure & how the code handles it.

### 5. Atomic Work Units
Break multi-step implementations into discrete, verifiable steps -- but once a plan is approved (Rule 2), execute its steps continuously; don't stop for a fresh approval after each one. Halt mid-plan only at a genuine decision point: a step reveals something the approved plan didn't anticipate (an unexpected error, a design assumption that turns out wrong, a file that doesn't match what the plan described), or a step is itself high-risk under `human-in-the-loop/SKILL.md`. Otherwise, verify each step's tool output as you go and summarize what was done at natural checkpoints or at the end -- not as a mandatory round-trip after every individual step. A plan that needs 5 approvals to execute 5 already-approved steps defeats the purpose of approving the plan in the first place.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-08-01* | *Last Reviewed: 2026-08-01*
