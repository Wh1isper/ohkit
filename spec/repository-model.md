# Repository Model

## Repository Surfaces

| Surface                         | Owner and purpose                                  |
| ------------------------------- | -------------------------------------------------- |
| `ohkit/`                        | Independently installable pure Python package      |
| `tests/`                        | Package behavior tests                             |
| `scripts/` and `scripts/tests/` | Repository and release tooling and tests           |
| `.github/`                      | CI, release workflows, and contribution automation |
| `spec/`                         | Accepted product and engineering contracts         |
| `docs/`                         | User documentation and operator procedures         |
| `.agents/skills/`               | Repository-local contributor workflows             |
| Root guides                     | Contribution, engineering, maintenance, security   |

Issues own unresolved design discussion. Pull requests review resulting changes. `.claude/skills` points to the same skills; `CLAUDE.md` points to `AGENTS.md`. These are aliases, not independent guidance copies.

## Package Boundary

Repository, distribution, and import names are `ohkit`. Python 3.13 is the minimum version. The bootstrap has no runtime dependencies. Wheels and source distributions contain package code, metadata, README, and license, not repository automation, Skills, or credentials. The source distribution can rebuild the wheel without Node.js or Rust. Installed package metadata owns `ohkit.__version__`.

## Release Boundary

Source manifests and lockfile retain version `0.0.0`. Tags `release/ohkit-vX.Y.Z` and `release/ohkit-vX.Y.Z-rc.N` select the release version; positive RC numbers have no leading zeroes. Release preparation modifies only the isolated checkout's manifest and lockfile. Python artifacts normalize RC versions to `X.Y.ZrcN`.

Build and publish are separate jobs. Only publication receives `ohkit-pypi` Environment secrets. That Environment accepts tags matching `release/ohkit-v*`. Published tags cannot be moved or deleted under the release ruleset. GitHub Releases follow successful PyPI publication; RC releases are marked prerelease. Operational steps are owned by [releasing](../docs/releasing.md).
