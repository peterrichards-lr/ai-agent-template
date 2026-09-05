# Active AI Agent Work State (Ephemeral Scratchpad)

> [!IMPORTANT]
> **Single Source of Truth**: All agent rules, architectural guidelines, and skill routing are defined in [`AGENTS.md`](./AGENTS.md).
> This file is gitignored and exists solely to maintain intra-task scratchpad context across AI provider switches (Gemini, Claude, Cursor, Copilot, etc.).
> On session startup or provider switch, read this file to discover active objectives and resume in-flight work.
>
> **Seeded, not authored**: `scripts/bootstrap_template.py` copies this scratchpad from the tracked template `.agents/templates/agent-state.md`.
> Edit the copy at the repository root freely; edit the template only when changing the starting structure for every new project.

---

## 1. Current Strategic Context & Objective

- **Repository**: `ai-agent-template`
- **Active Git Branch**: `main`
- **Objective**: [State the single active objective this session is working toward.]
- **Status**: Not started.

---

## 2. Active Task Checklist

Work items for the current objective. Keep this list short and current; completed
objectives should be cleared rather than accumulated (see `AGENTS.md` section 3).

- [ ] [Task 1: description, linked GitHub issue, and acceptance criteria.]
- [ ] [Task 2: ...]

---

## 3. Blockers & Open Questions

Anything preventing progress, plus questions awaiting a human decision. An empty
list here means work is unblocked.

- [None recorded.]

---

## 4. Session Handoff Notes

Context a different agent (or a later session) would otherwise have to rediscover:
key file paths, decisions already made and rejected, and commands already verified.

- [None recorded.]

---

## 5. What Does Not Belong Here

- **Technical debt**: tracked solely as GitHub issues labelled `tech-debt` (see `.agents/skills/github-workflow/SKILL.md` rule 4). Do not maintain a debt table in this file.
- **Durable rules and conventions**: belong in `AGENTS.md` and `.agents/skills/`, not in this ephemeral scratchpad.
- **Secrets, tokens, or credentials**: never record them here, gitignored or not.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
