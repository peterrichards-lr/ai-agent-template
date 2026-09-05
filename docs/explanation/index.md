# Explanation

**Understanding-oriented.** Explanation is the discursive half of the
documentation: architecture, trade-offs, history, the reasons a decision went the
way it did and what the alternative would have cost. It is read away from the
keyboard.

## What belongs here

- Architecture overviews and the reasoning behind them.
- Design decisions, the options rejected, and why.
- Incident post-mortems whose lesson outlives the incident.
- Background a reader needs to make good judgement calls.

## What does not

| If the page... | It belongs in |
| --- | --- |
| Gets a newcomer to a first working result | [`docs/tutorials/`](../tutorials/index.md) |
| Answers "how do I ...?" | [`docs/how-to/`](../how-to/index.md) |
| Lists options exhaustively | [`docs/reference/`](../reference/index.md) |

## Choosing a division

The four divisions come from the [Diátaxis](https://diataxis.fr) model, and the
split is along two axes: whether the reader is *studying* or *working*, and
whether the page serves *practice* or *theory*.

| | Practical steps | Theoretical knowledge |
| --- | --- | --- |
| **Studying** (acquiring skill) | Tutorials | Explanation |
| **Working** (applying skill) | How-to guides | Reference |

Two questions settle almost every case:

1. Does the reader have a goal already? If no, it is a tutorial. If yes, it is a
   how-to guide.
2. Is the page consulted or read? Consulted means reference; read means
   explanation.

A page that resists classification is usually two pages. Split it and cross-link
them — that is nearly always the right answer, and it is the mistake this
structure exists to prevent.

## Writing rules

- Admit uncertainty and record what was rejected; a decision without its
  alternatives is not an explanation.
- Do not smuggle in instructions. If a reader could follow the page at a
  terminal, the instructions belong in a how-to guide.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
