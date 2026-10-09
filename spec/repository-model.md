# Repository Model

## Repository Surfaces

| Surface                         | Owner and purpose                                       |
| ------------------------------- | ------------------------------------------------------- |
| `ohkit/`                        | Independently installable pure Python package           |
| `tests/`                        | Package behavior tests                                  |
| `scripts/` and `scripts/tests/` | Repository and release tooling and tests                |
| `.github/`                      | CI, release workflows, and contribution automation      |
| `spec/`                         | Accepted product and engineering contracts              |
| `docs/`                         | User documentation, navigation, and operator procedures |
| `website/`                      | Independent static documentation build and presentation |
| `.agents/skills/`               | Repository-local contributor workflows                  |
| Root guides                     | Contribution, engineering, maintenance, security        |

Issues own unresolved design discussion. Pull requests review resulting changes. `.claude/skills` points to the same skills; `CLAUDE.md` points to `AGENTS.md`. These are aliases, not independent guidance copies.

## Documentation Boundary

`docs/` owns user-facing Markdown, conceptual examples labeled as unimplemented, and operator procedures; its `meta.json` files own navigation. The independent Fumadocs application in `website/` owns presentation and the canonical site address, `https://ohkit.wh1isper.top/`. Next.js exports static output into ignored `website/out/`; no production Node.js service is required. `website/package.json` and its pnpm lockfile own the documentation build toolchain, independently of the Python package's runtime and artifact build. The website does not depend on a13n packages. Existing documentation routes remain stable across presentation changes.

The documentation workflow builds and validates pull-request content without deployment credentials. Deployment requires an explicit repository publication opt-in, uses the `docs` GitHub Environment restricted to `main`, and uploads the successful build artifact to Cloudflare Pages. A separate manual main-only workflow can create or verify the Pages project without uploading a deployment. Python publication remains a separate workflow and Environment. [Documentation maintenance](../docs/documentation.md) owns operational configuration and required secrets.

## Package Boundary

Repository, distribution, and import names are `ohkit`. Python 3.13 is the minimum version. WebSocket transport support is included in the default installation through the `websockets` runtime dependency. Backend SDKs may use optional extras; shared values and execution remain independent of backend SDKs. Wheels and source distributions contain package code, metadata, README, and license, not repository automation, Skills, or credentials. The source distribution can rebuild the wheel without Node.js or Rust. Installed package metadata owns `ohkit.__version__`.

## Release Boundary

Source manifests and lockfile retain version `0.0.0`. Tags `release/ohkit-vX.Y.Z` and `release/ohkit-vX.Y.Z-rc.N` select the release version; positive RC numbers have no leading zeroes. Release preparation modifies only the isolated checkout's manifest and lockfile. Python artifacts normalize RC versions to `X.Y.ZrcN`.

Build and publish are separate jobs. Only publication receives `ohkit-pypi` Environment secrets. That Environment accepts tags matching `release/ohkit-v*`. Published tags cannot be moved or deleted under the release ruleset. GitHub Releases follow successful PyPI publication; RC releases are marked prerelease. Operational steps are owned by [releasing](../docs/releasing.md).
