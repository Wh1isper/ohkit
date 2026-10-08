---
title: Documentation maintenance
description: Write, preview, validate, and deploy the ohkit documentation site.
---

## Repository layout

`docs/` owns Markdown content and examples. The root `mkdocs.yml` owns navigation, theme, and the canonical site address. MkDocs Material renders a static site into ignored `site/`. There is no separate frontend application or production Python server.

The canonical address is `https://ohkit.wh1isper.top/`. The documentation toolchain is in the `docs` dependency group of `pyproject.toml` and is pinned by `uv.lock`. It is not a Python package runtime or build dependency.

## Write a page

1. Add a Markdown file under `docs/`.
2. Include `title` and `description` front matter. Do not repeat the title as a top-level heading; the site renders it.
3. Use relative Markdown file links for other documentation pages. Use repository URLs for specifications and contributor guides outside `docs/`.
4. Add the page to `nav` in `mkdocs.yml`. Navigation has one owner; do not add a second `meta.json` catalog.
5. Use short, precise English prose. Keep each paragraph on one source line. Use fenced code blocks and Mermaid diagrams when they clarify a flow.
6. Clearly distinguish shipped behavior from conceptual examples. Do not document proposed imports as available APIs.
7. Format Markdown and build the site before submitting the change.

These writing and validation conventions follow a13n's documentation standards without importing its frontend application stack.

## Preview and validate

Install Python 3.13 and uv, then run:

```bash
make docs-serve
```

Open the local address printed by MkDocs, normally `http://127.0.0.1:8000`. To select another local port:

```bash
make docs-serve DOCS_ADDR=127.0.0.1:8001
```

Build the static site:

```bash
make docs-build
```

The strict build fails on missing pages, invalid navigation, and broken internal anchors. Search, code highlighting, and diagrams are static-site features; no model credentials or application service are required.

## GitHub Environment

Use the `docs` Environment in `Wh1isper/ohkit`, restricted to the `main` branch. Add these Environment secrets yourself:

| Secret                  | Value                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------- |
| `CLOUDFLARE_API_TOKEN`  | API token with **Account → Cloudflare Pages → Edit**, restricted to the target account |
| `CLOUDFLARE_ACCOUNT_ID` | ID of the Cloudflare account that owns the Pages project                               |

No runtime environment variables are required for the static site. The public domain is in `mkdocs.yml`; the Pages project name is `ohkit-docs`. Do not put either secret in Markdown, repository files, or chat.

The repository Actions variable `DOCS_DEPLOY_ENABLED` controls publication. Leave it unset or `false` while provisioning; set it to exactly `true` only when documentation publication is authorized. Project creation does not change this switch.

## Cloudflare setup

1. Add the Environment secrets listed above.
2. Run the **Create docs project** GitHub Actions workflow on `main`. It creates a Cloudflare Pages **Direct Upload** project named `ohkit-docs`, with production branch `main`, or verifies a matching existing project without changing it. It does not upload a deployment or modify DNS. Direct Upload keeps GitHub Actions as the only build and upload owner.
3. After the first authorized deployment, add `ohkit.wh1isper.top` under the Pages project's **Custom domains** and follow Cloudflare's domain verification and DNS instructions. Register the custom domain with Pages; a DNS record alone is not the complete binding.
4. Confirm HTTPS and the custom domain show as active, then verify the homepage, search, and example page.

An authenticated maintainer can also create the project with Wrangler:

```bash
npx wrangler pages project create ohkit-docs --production-branch main
```

Do not execute project creation or deployment without the corresponding authorization. Creating the GitHub Environment, configuring secrets, and creating the Pages project do not publish the site. If creation reports a transport error, inspect the project before retrying; a missing acknowledgement is not proof that no project was created.

## Deployment workflow

The `Docs` GitHub Actions workflow builds documentation on relevant pull requests and `main` pushes. It stores `site/` as an artifact. Only a successful `main` push build with `DOCS_DEPLOY_ENABLED=true` can deploy, and only its deployment job receives the `docs` Environment secrets. A manual workflow dispatch builds an artifact without deploying.

The Python release workflow remains separate and uses the `ohkit-pypi` Environment. Documentation publication never publishes a Python release.

A deployment uploads the already built artifact to the `ohkit-docs` Pages project. Inspect the workflow result and Pages deployment before retrying an uncertain upload. The repository Website field is a link, not evidence that DNS or deployment is ready.
