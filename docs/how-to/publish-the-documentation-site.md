# Publish the Documentation Site

The MkDocs Material site is optional. Nothing in this repository builds or
deploys it until you ask for it.

This guide is kept whether or not the site was enabled at bootstrap, because the
decision is reversible. If `mkdocs.yml` is not in the repository, the site was
never turned on: copy `mkdocs.yml`, `.github/workflows/docs.yml` and
`requirements-docs.txt` back from the template and apply the two edits
`--docs-site` would have made, described below.

## Turn it on during bootstrap

```bash
python3 scripts/bootstrap_template.py \
  --name my-awesome-app \
  --lang go \
  --repo-owner my-org \
  --conduct-email conduct@example.com \
  --docs-site
```

`--docs-site` does two things:

1. Seeds `site_name`, `site_url` and `repo_url` in `mkdocs.yml` from `--name` and
   `--repo-owner`.
2. Uncomments the `push:` trigger in `.github/workflows/docs.yml`, which ships
   commented out so that a project that did not opt in never deploys.

Without `--docs-site`, `--clean-template` deletes `mkdocs.yml`,
`.github/workflows/docs.yml` and `requirements-docs.txt`. The Diátaxis
directories under `docs/` are kept either way — organising documentation by
division is worth doing whether or not it is ever rendered.

## Enable GitHub Pages

The workflow deploys with `actions/deploy-pages`, which requires the repository
to be serving Pages from Actions. This is not the default, and the template
deliberately does not assume it:

1. Settings → Pages → **Source: GitHub Actions**.
2. Push to `main`, or run the **Deploy Documentation** workflow manually from the
   Actions tab.

Until step 1 is done, the deploy job fails with `Get Pages site failed`. That is
the correct failure: it is loud, and it does not touch a live site.

## Preview locally

```bash
pip install -r requirements-docs.txt
cp README.md docs/index.md
mkdocs serve
```

`docs/index.md` is the site home page and is **generated** from `README.md` at
build time — the workflow runs the same `cp` — so the project's landing page is
never maintained in two places. It is gitignored; do not commit it.

## Add a page

Decide which Diátaxis division the page belongs to before writing it. The
decision table is in [Explanation](../explanation/index.md), and the short
version an agent follows is in `.agents/skills/documentation/SKILL.md`.

Then add the file, add it to `nav:` in `mkdocs.yml`, and run the documentation
gate:

```bash
python3 scripts/append_timestamps.py
python3 scripts/check_docs_review.py
```

Nested directories are handled, so `docs/how-to/deployment/blue-green.md` gets
its footer like any top-level page.

## Timestamp footers are shown, not hidden

Every Markdown file in this repository ends with a
`*Last Updated* | *Last Reviewed*` footer, and those footers render on the
published site on purpose. They are the repository's freshness contract, and the
site is where readers can act on it — a page last reviewed two years ago should
say so to the person about to trust it. Hiding them would need CSS targeting the
final `<hr>` of every page, which breaks the moment a page legitimately ends in a
horizontal rule.

<!-- markdownlint-disable MD049 -->
---
*Last Updated: 2026-09-05* | *Last Reviewed: 2026-09-05*
