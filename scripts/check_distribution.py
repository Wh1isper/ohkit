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
        assert prefix + "licenses/LICENSE" in names
        assert all(name.startswith(("ohkit/", prefix)) for name in names), names
        metadata = email.message_from_bytes(archive.read(prefix + "METADATA"))
        assert metadata["Name"] == "ohkit"
        assert metadata["Version"] == version
        assert metadata["Requires-Python"] == ">=3.13"
        assert metadata["License-Expression"] == "Apache-2.0"
        assert not metadata.get_all("Requires-Dist")
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
                f"import ohkit; assert ohkit.__version__ == {version!r}; print(ohkit.__version__)",
            ],
            check=True,
            cwd=work,
        )
    print(f"Validated ohkit {version}: wheel, sdist rebuild, and isolated import")


if __name__ == "__main__":
    main()
