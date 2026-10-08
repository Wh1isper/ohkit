"""Check source version and local Markdown file links (excluding fragments)."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main() -> None:
    root = Path.cwd()
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    assert project["name"] == "ohkit" and project["version"] == "0.0.0"
    assert (root / "CLAUDE.md").resolve() == root / "AGENTS.md"
    assert (root / ".claude/skills").resolve() == root / ".agents/skills"
    files = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], text=True
    ).split("\0")
    errors = []
    for name in set(files):
        path = root / name
        if path.suffix != ".md" or path.is_symlink():
            continue
        text = re.sub(r"(?ms)^```.*?^```[^\n]*", "", path.read_text())
        for link in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", text):
            target = urlsplit(link)
            if target.scheme or target.netloc or not target.path or "<" in target.path:
                continue
            if not (path.parent / unquote(target.path)).exists():
                errors.append(f"{name}: missing {link}")
    if errors:
        raise SystemExit("\n".join(sorted(errors)))
    print("Repository version, guidance aliases, and Markdown file links are valid")


if __name__ == "__main__":
    main()
