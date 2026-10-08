---
title: Documentation maintenance
description: Write, preview, validate, and deploy the ohkit documentation site.
---

## Repository layout

`docs/` owns Markdown content, examples, and `meta.json` navigation. The independent `website/` application uses Fumadocs and Next.js to export a static site into ignored `website/out/`. It needs no production Node.js service and has no dependency on a13n packages.

The canonical address is `https://ohkit.wh1isper.top/`, configured in `website/lib/site.tsx`. The documentation toolchain is pinned by `website/package.json` and `website/pnpm-lock.yaml`. Node.js is a documentation build tool, not a Python package runtime or artifact build dependency.

## Write a page

1. Add a Markdown file under `docs/`.
2. Include `title` and `description` front matter. Do not repeat the title as a top-level heading; the site renders it.
3. Use relative Markdown file links for other documentation pages. Use repository URLs for specifications and contributor guides outside `docs/`.
4. Add the page to the relevant `docs/**/meta.json` file. Navigation has one owner; do not maintain a second catalog in the website.
5. Use short, precise English prose. Keep each paragraph on one source line. Use fenced code blocks and Mermaid diagrams when they clarify a flow.
6. Clearly distinguish shipped behavior from conceptual examples. Do not document proposed imports as available APIs.
7. Format Markdown and build the site before submitting the change.

Keep `.md` pages readable on GitHub as well as on the site. The site resolves relative Markdown links to public routes. React components belong in `website/`, not ordinary prose pages.

## Diagrams

Use fenced `mermaid` blocks. They render as SVG in the browser with a shared light/dark palette, rounded nodes, and restrained connectors. Add `accTitle` and `accDescr` to explain a diagram to assistive technology. Prefer concise node labels and top-down flows for wide branching diagrams; do not hardcode theme colors or add executable callbacks.

Diagrams sit in a keyboard-scrollable panel with an **Expand** dialog and a **View Mermaid source** fallback. Check both themes and a narrow viewport after changing a diagram. The static build validates page links, but does not execute browser-side Mermaid; visual inspection is still required.

## Preview and validate

Install Node.js 24 and pnpm 10.30.3, then run:

```bash
make docs-serve
```

Open the local address printed by Next.js, normally `http://127.0.0.1:3000`. To select another local port:

```bash
make docs-serve DOCS_PORT=3001
```

Build the static site:

```bash
make docs-build
```

This installs the frozen lockfile, exports the site, checks internal links and anchors, tests public routes and navigation entries, and runs TypeScript checks. Search uses a build-time index exported at `/api/search`; despite the path name, there is no live API server. Code highlighting is built into the HTML; diagrams render in the browser. No model credentials or application service are required.

## GitHub Environment

Use the `docs` Environment in `Wh1isper/ohkit`, restricted to the `main` branch. Add these Environment secrets yourself:

| Secret                  | Value                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------- |
| `CLOUDFLARE_API_TOKEN`  | API token with **Account → Cloudflare Pages → Edit**, restricted to the target account |
| `CLOUDFLARE_ACCOUNT_ID` | ID of the Cloudflare account that owns the Pages project                               |

No runtime environment variables are required for the static site. The public domain is in `website/lib/site.tsx`; the Pages project name is `ohkit-docs`. Do not put either secret in Markdown, repository files, or chat.

The repository Actions variable `DOCS_DEPLOY_ENABLED` controls publication. Leave it unset or `false` while provisioning; set it to exactly `true` only when documentation publication is authorized. Project creation does not change this switch.

## Cloudflare setup

1. Add the Environment secrets listed above.
2. Run the **Create docs project** GitHub Actions workflow on `main`. It creates a Cloudflare Pages **Direct Upload** project named `ohkit-docs`, with production branch `main`, or verifies a matching existing project without changing it. It does not upload a deployment or modify DNS. Direct Upload keeps GitHub Actions as the only build and upload owner.
3. After the first authorized deployment, run **Configure docs domain** on `main` to register `ohkit.wh1isper.top` with Pages and create its CNAME to `ohkit-docs.pages.dev` if absent. For automatic DNS setup, the token additionally needs **Zone → Zone → Read** and **Zone → DNS → Edit**, restricted to `wh1isper.top`. Existing conflicting DNS records are not overwritten. The workflow is manual, uses the `docs` Environment, and does not deploy site content.
4. If DNS permissions are unavailable, registration can succeed while the workflow reports a DNS failure. Add the CNAME in the DNS provider instead, or update the Environment token and rerun. A DNS record alone is not the complete Pages binding. You can also register the domain manually under the Pages project's **Custom domains**.
5. Confirm HTTPS and the custom domain show as active, then verify the homepage, search, and example page. A successful configuration request can still report pending certificate or domain activation.

An authenticated maintainer can also create the project with Wrangler:

```bash
npx wrangler pages project create ohkit-docs --production-branch main
```

Do not execute project creation or deployment without the corresponding authorization. Creating the GitHub Environment, configuring secrets, and creating the Pages project do not publish the site. If creation reports a transport error, inspect the project before retrying; a missing acknowledgement is not proof that no project was created.

## Deployment workflow

The `Docs` GitHub Actions workflow builds documentation on relevant pull requests and `main` pushes. It stores `website/out/` as an artifact. Only a successful `main` push build with `DOCS_DEPLOY_ENABLED=true` can deploy, and only its deployment job receives the `docs` Environment secrets. A manual workflow dispatch builds an artifact without deploying.

The Python release workflow remains separate and uses the `ohkit-pypi` Environment. Documentation publication never publishes a Python release.

A deployment uploads the already built artifact to the `ohkit-docs` Pages project. Inspect the workflow result and Pages deployment before retrying an uncertain upload. The repository Website field is a link, not evidence that DNS or deployment is ready.
