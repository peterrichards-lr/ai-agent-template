# Tutorials

**Learning-oriented.** A tutorial takes a beginner through a complete, working
result, start to finish, holding their hand the whole way. Success is measured
by "did they get the thing working?", not by "did they understand every option?".

## What belongs here

- A first-run walkthrough: clone, bootstrap, see something work.
- An end-to-end path through one realistic scenario, with every command spelled out.
- Exactly one route to the goal. A tutorial that says "or, alternatively..." has
  become a how-to guide.

## What does not

| If the page... | It belongs in |
| --- | --- |
| Assumes the reader already has a goal and needs the steps | [`docs/how-to/`](../how-to/index.md) |
| Enumerates every flag, field or option | [`docs/reference/`](../reference/index.md) |
| Argues for a design decision | [`docs/explanation/`](../explanation/index.md) |

## Writing rules

- Second person, imperative: "Run `pytest -v`", not "the tests can be run".
- Every command is copy-pasteable and shown with its expected output.
- No unexplained detours. If the reader must understand something first, link to
  the explanation rather than inlining it.

Delete this page once the section has real content, or keep it as the section
landing page and list the tutorials beneath it.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
