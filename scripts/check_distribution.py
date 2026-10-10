"""Validate both published artifacts and an isolated installation; publish nothing."""

from __future__ import annotations

import email
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path


def check_wheel(path: Path, version: str) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        prefix = f"ohkit-{version}.dist-info/"
        assert "ohkit/py.typed" in names
        assert "ohkit/__init__.py" in names
        assert "ohkit/execution.py" in names
        for backend in ("codex", "acp", "claude"):
            assert f"ohkit/backends/{backend}/backend.py" in names
        assert prefix + "licenses/LICENSE" in names
        assert all(name.startswith(("ohkit/", prefix)) for name in names), names
        metadata = email.message_from_bytes(archive.read(prefix + "METADATA"))
        assert metadata["Name"] == "ohkit"
        assert metadata["Version"] == version
        assert metadata["Requires-Python"] == ">=3.13"
        assert metadata["License-Expression"] == "MIT AND Apache-2.0"
        assert "ohkit/backends/codex/_generated.py" in names
        assert "Apache License" in archive.read(prefix + "licenses/third-party/codex/LICENSE").decode()
        assert "Codex" in archive.read(prefix + "licenses/third-party/codex/NOTICE").decode()
        assert prefix + "licenses/THIRD_PARTY_NOTICES.md" in names
        license_text = archive.read(prefix + "licenses/LICENSE").decode()
        assert license_text.startswith("MIT License\n")
        assert "Copyright (c) 2026 Converge AI" in license_text
        assert metadata.get_all("Requires-Dist", []) == [
            "agent-client-protocol<0.13,>=0.12.1",
            "claude-agent-sdk<0.3,>=0.2.165",
            "pydantic<3,>=2.12",
            "websockets<16,>=15",
        ]
        assert metadata.get_all("Provides-Extra", []) == []
        assert "Root-Is-Purelib: true" in archive.read(prefix + "WHEEL").decode()


def rebuild_sdist(sdist: Path, work: Path, version: str) -> Path:
    with tarfile.open(sdist) as archive:
        names = {item.name for item in archive.getmembers() if item.isfile()}
        base = f"ohkit-{version}/"
        assert base + "ohkit/py.typed" in names
        assert base + "LICENSE" in names
        root_files = {
            base + item
            for item in ("pyproject.toml", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "PKG-INFO", ".gitignore")
        }
        assert all(name.startswith((base + "ohkit/", base + "third-party/")) or name in root_files for name in names), (
            names
        )
        archive.extractall(work, filter="data")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(work / "rebuilt"), str(work / f"ohkit-{version}")],
        check=True,
        cwd=work,
    )
    return work / "rebuilt" / f"ohkit-{version}-py3-none-any.whl"


def check_install(wheel: Path, work: Path, version: str) -> None:
    environment = work / "venv"
    subprocess.run(["uv", "venv", "--python", sys.executable, str(environment)], check=True, cwd=work)
    interpreter = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(["uv", "pip", "install", "--python", str(interpreter), str(wheel)], check=True, cwd=work)
    subprocess.run(
        [
            str(interpreter),
            "-I",
            "-c",
            f"""import ohkit
from ohkit import Thread, Run, NativeData
from ohkit.backends.codex import Codex
from ohkit.backends.acp import ACP, ACPOptions
from ohkit.backends.claude import Claude
from websockets.asyncio.client import connect
assert ohkit.__version__ == {version!r}
assert callable(connect)
assert Codex().capabilities.steer
assert ACP(options=ACPOptions(command=('agent',)))
assert Claude().capabilities.resume and not Claude().capabilities.steer
assert NativeData('codex', '{{"ok":true}}').decode() == {{'ok': True}}
print(ohkit.__version__)
""",
        ],
        check=True,
        cwd=work,
    )


def main() -> None:
    root = Path.cwd()
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    dist = root / "dist"
    wheel = dist / f"ohkit-{version}-py3-none-any.whl"
    sdist = dist / f"ohkit-{version}.tar.gz"
    assert sorted(path.name for path in dist.iterdir() if path.is_file() and not path.name.startswith(".")) == sorted(
        [wheel.name, sdist.name]
    )
    check_wheel(wheel, version)
    with tempfile.TemporaryDirectory(prefix="ohkit-dist-") as temporary:
        work = Path(temporary)
        check_wheel(rebuild_sdist(sdist, work, version), version)
        check_install(wheel, work, version)
    print(f"Validated ohkit {version}: wheel, sdist rebuild, isolated install with all backend imports")


if __name__ == "__main__":
    main()
