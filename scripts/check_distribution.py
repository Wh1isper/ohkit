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
        assert "ohkit/backends/codex/backend.py" in names
        assert prefix + "licenses/LICENSE" in names
        assert all(name.startswith(("ohkit/", prefix)) for name in names), names
        metadata = email.message_from_bytes(archive.read(prefix + "METADATA"))
        assert metadata["Name"] == "ohkit"
        assert metadata["Version"] == version
        assert metadata["Requires-Python"] == ">=3.13"
        assert metadata["License-Expression"] == "MIT"
        license_text = archive.read(prefix + "licenses/LICENSE").decode()
        assert license_text.startswith("MIT License\n")
        assert "Copyright (c) 2026 Converge AI" in license_text
        requirements = metadata.get_all("Requires-Dist", [])
        assert requirements and all(
            "extra == 'codex-websocket'" in item or 'extra == "codex-websocket"' in item for item in requirements
        )
        assert not any("a13n" in item or "pydantic" in item for item in requirements)
        assert "Root-Is-Purelib: true" in archive.read(prefix + "WHEEL").decode()


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
        with tarfile.open(sdist) as archive:
            names = {item.name for item in archive.getmembers() if item.isfile()}
            base = f"ohkit-{version}/"
            assert base + "ohkit/py.typed" in names
            assert base + "LICENSE" in names
            assert all(
                name.startswith(base + "ohkit/")
                or name
                in {base + item for item in ("pyproject.toml", "README.md", "LICENSE", "PKG-INFO", ".gitignore")}
                for name in names
            ), names
            archive.extractall(work, filter="data")
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(work / "rebuilt"), str(work / f"ohkit-{version}")],
            check=True,
            cwd=work,
        )
        check_wheel(work / "rebuilt" / wheel.name, version)
        environment = work / "venv"
        subprocess.run(["uv", "venv", "--python", sys.executable, str(environment)], check=True, cwd=work)
        interpreter = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            ["uv", "pip", "install", "--python", str(interpreter), "--no-deps", str(wheel)], check=True, cwd=work
        )
        subprocess.run(
            [
                str(interpreter),
                "-I",
                "-c",
                f"""import asyncio, importlib.util, ohkit
from ohkit import Thread, Run, NativeData, UnavailableError
from ohkit.backends.codex import Codex, CodexOptions
assert ohkit.__version__ == {version!r}
assert importlib.util.find_spec('websockets') is None
assert Codex().capabilities.steer
assert NativeData('codex', '{{"ok":true}}').decode() == {{'ok': True}}
async def missing_extra():
    try:
        async with Codex(options=CodexOptions(websocket_url='ws://127.0.0.1:1', history_scope='test')):
            raise AssertionError('Optional dependency unexpectedly available')
    except UnavailableError as error:
        assert 'codex-websocket' in str(error)
asyncio.run(missing_extra())
print(ohkit.__version__)
""",
            ],
            check=True,
            cwd=work,
        )
        subprocess.run(
            ["uv", "pip", "install", "--python", str(interpreter), str(wheel) + "[codex-websocket]"],
            check=True,
            cwd=work,
        )
        subprocess.run(
            [
                str(interpreter),
                "-I",
                "-c",
                "from ohkit.backends.codex import Codex; from websockets.asyncio.client import connect; assert callable(connect)",
            ],
            check=True,
            cwd=work,
        )
    print(f"Validated ohkit {version}: wheel, sdist rebuild, isolated core and optional transport installs")


if __name__ == "__main__":
    main()
