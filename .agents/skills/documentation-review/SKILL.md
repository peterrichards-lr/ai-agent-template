---
name: documentation-review
description: >-
  Governs auditing an existing documentation set: measuring before diagnosing, inspecting rendered
  output, checking documents against the code, and fixing routing before restructuring.
  Load when reviewing or restructuring docs as a body of work, or when told they are
  overwhelming, stale, or hard to navigate.
---

# Skill: Documentation Review & Audit

> [!NOTE]
> **Sibling to [`documentation`](../documentation/SKILL.md), not a replacement.**
> That skill governs *hygiene after a change* -- timestamp footers, post-implementation
> verification, remediating a doc that a new feature left missing. This one governs
> *auditing the set as a whole*. Reach for that one after you change code; reach for this
> one when the documentation itself is the work.

A method, in order. The sequence matters more than any individual step: steps 2
and 3 find defects that no amount of reading finds, and doing step 5 first
produces a tidy reorganisation of documents that are still wrong.

## 1. Measure before you diagnose

Do **not** start from the premise you were handed -- "there is too much of it",
"it is out of date", "it is overwhelming". Count first:

- number of documents, total word count, words per section
- the largest documents, and where they sit

Then compare against the class of project. Most documentation that *feels*
overwhelming is not large. A set of ~50 documents and ~70,000 words is small;
comparable tools run to several hundred thousand words. If volume is not the
problem, say so explicitly and go and find what is.

Three usual culprits, in order of likelihood:

1. **No routing layer** -- sections with no landing page, so a reader arrives at
   a flat list of N items and must read all N before choosing.
2. **Rendering defects** -- the published output differs from what the source
   appears to say.
3. **Documents that contradict the code.**

## 2. Inspect the OUTPUT, not the source

This step finds what nothing else finds.

If the documentation is published through any build step -- a static site
generator, a man page, generated API reference, a PDF -- **build it and examine
the artefact**. Grep the rendered output for markup that should have been
consumed:

```bash
# markup that survived into the rendered page
grep -rho '\[!\(NOTE\|IMPORTANT\|TIP\|WARNING\|CAUTION\)\]' <output-dir> --include='*.html'

# diagrams that rendered as code blocks instead of diagrams
grep -rho 'class="language-[a-z]*"' <output-dir> --include='*.html' | sort | uniq -c
```

Reading the configuration will tell you which extensions are enabled. Only the
output tells you that 57 alert blocks rendered as plain quotes with the marker
text visible to readers -- disproportionately the warnings, which are the most
load-bearing sentences in any documentation set.

Also **read the build's own warnings.** Broken anchors and dead links are
reported there on every run and routinely scrolled past.

If there is no build step, the equivalent is to view the documents the way a
reader does -- in the rendering the audience actually uses -- not in an editor.

## 3. Check the documents against the CODE

Take every factual claim about a default, a flag, a path, a port, a version, or
a file name, and verify it against the source that implements it.

Do **not** check documents against each other. Two documents can agree and both
be wrong. Verify against the implementation.

Expect contradictions in *both* directions. A real audit found one document
claiming a default was X when the code said Y, and a second claiming the same
setting was Y when the code said X -- so no single systematic correction would
have fixed either. It also found a flag advertised for years that had never
existed in the codebase, and a documented configuration layer that was read only
in one unrelated code path.

### For anything documenting a command-line interface

**Render the help; do not read the source.** Build the parser in-process and
print it, or invoke the tool's own help in a controlled way.

This single habit found two live product bugs during what was scoped as a
documentation review: a flag that was permanently enabled on every command, and
a guide command printing a configuration hierarchy that was wrong on every level
while recommending a command the tool refuses.

The rule already exists in most test guidance -- *assertions about runtime
behaviour must be observed, not inferred* -- and applies just as much to
documentation surfaces.

## 4. Treat a filed issue's stated cause as a hypothesis

If you are working from an issue, **re-derive its numbers before changing the
file it names.**

An issue confidently identified the wrong file. Its conclusion was right and its
cause was not, so implementing it as written would have shipped, passed its own
tests, and left the defect in place. One command established the truth.

When the diagnosis turns out wrong, correct the issue *before* opening the pull
request, so the record and the fix agree.

## 5. Fix routing before restructuring

If the documentation already follows a framework -- Diataxis (tutorials /
how-to / reference / explanation) or similar -- **do not restructure it.** That
is the hard part and it is usually already right.

What is usually missing is the routing layer:

- **A landing page per section**, saying what the section is for and grouping
  its contents with one line on when to pick each.
- **Grouped navigation** rather than a flat list. Twenty undifferentiated items
  are harder to navigate than two hundred organised ones, because the reader
  must read all twenty to choose.
- **The entry point reachable from where people arrive.** Check the front-door
  document is linked from the repository README, not only from a generated
  navigation menu. A tutorial reachable only from the site's sidebar is
  invisible to anyone reading on the code host.
- **An intent layer** -- "I want to…" -- above any subject index, routing on the
  reader's question rather than on your taxonomy.

**Verify coverage programmatically, not by eye.** Parse each landing page for
links and diff against the files on disk. A silently omitted page is the exact
failure this work would otherwise introduce.

**Beware creating a second taxonomy.** If the home page organises by subject
while the navigation organises by framework, a reader learns one and meets the
other on their first click. Either make the relationship explicit in a sentence,
or pick one.

## 6. Include the surfaces that do not look like documentation

Anything user-facing counts, and the ones that ship inside the product rot
fastest because nothing treats them as documentation:

- man pages
- `--help` / usage strings
- any message the program prints containing a URL or a file path
- onboarding, guide or "getting started" commands built into the tool
- error messages that tell the user what to do next

Two checks worth running every time:

- **Every printed URL must resolve.** Three links printed by one tool had been
  404s since a file rename, two of them on failure paths -- so a user already
  having a bad time was handed a dead link.
- **Beware an auto-stamped date.** A document whose "last updated" date is
  rewritten by tooling or a release process advertises freshness it does not
  have. That is worse than having no date, because it actively misleads.

  This repository stamps footers with `scripts/append_timestamps.py` and checks
  staleness with `scripts/check_docs_review.py`. Those two fields do different
  jobs and must not collapse into one: *Last Updated* may be written by tooling,
  but *Last Reviewed* only means anything if a human moved it. A review date a
  script can advance is not a review date.

  Check the surfaces that script does not reach. It globs markdown; a man page,
  a generated reference, or a help string carries no footer and so is invisible
  to the staleness gate entirely.

## 7. Guard the class, not the instance

For every defect found, add a check that fails if it recurs, and assert the
**class** rather than the example: *"no flag anywhere may render as a
positional"*, not *"this flag is fine"*.

Then **break it deliberately and confirm the guard fails.** A test that has
never failed has not been shown to test anything. Doing this on every guard
revealed one that protected against an input the code could never produce --
discoverable only by trying to trigger it.

## 8. Traps that are easy to walk into

- **Anchors differ between renderers.** A heading containing an emoji, an
  ampersand or punctuation slugifies differently on a code host than in a static
  site generator, so a relative link can be correct on only one at a time. The
  fix is removing the character from *linked* headings, not picking a side. Note
  only one direction is noisy: the site build warns about a missing anchor, but
  nothing warns when the link works on the site and is broken on the code host.
- **Know which renderer a link targets.** A link to a code host's file view uses
  *that host's* slugifier. "Fixing" its anchor to match your generated site
  breaks a link that worked.
- **Cross-platform script pairs must stay at parity.** Where a `.sh` and a
  `.ps1` (or equivalent) exist, every assertion added to one goes into the other
  in the same change. Parity maintained by habit fails the moment the person
  maintaining it changes.
- **Renaming a file changes its published URL.** Without a redirect mechanism,
  prefer changing the *label* and *navigation position*: that is what a reader
  sees, and the path is internal. Renaming also breaks every inbound link, which
  must all be enumerated first.
- **Never record an exact count in prose.** "Documents 42 of 238 options" was
  wrong in both terms and had been for years; a corrected "54 of 246" was stale
  before the change that introduced it had even merged. State the relationship
  and give the command to measure it.

## Reporting

Report **what you measured**, not what you changed. Before and after numbers for
each defect.

Where you chose not to act, say why -- a deliberate, recorded decision is a
legitimate outcome; an unnoticed omission is not.

Where you were wrong earlier in the work, correct it explicitly rather than
quietly, including in issues and pull request descriptions you have already
written.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-20* | *Last Reviewed: 2026-09-20*
