from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

COMPONENTS = ("ohkit",)
RELEASE_VERSION_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-rc\.(?P<rc>[1-9][0-9]*))?"
)


class ReleaseVersionError(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseVersion:
    major: int
    minor: int
    patch: int
    rc: int | None

    @property
    def canonical(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.rc is None:
            return base
        return f"{base}-rc.{self.rc}"

    @property
    def python_package(self) -> str:
        if self.rc is None:
            return self.canonical
        return f"{self.major}.{self.minor}.{self.patch}rc{self.rc}"

    @property
    def is_prerelease(self) -> bool:
        return self.rc is not None

    @property
    def precedence_key(self) -> tuple[int, int, int, int, int]:
        if self.rc is None:
            return self.major, self.minor, self.patch, 1, 0
        return self.major, self.minor, self.patch, 0, self.rc


def parse_release_version(version: str) -> ReleaseVersion:
    match = RELEASE_VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ReleaseVersionError(f"Release version must use X.Y.Z or X.Y.Z-rc.N syntax: {version}")
    rc = match.group("rc")
    return ReleaseVersion(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        rc=int(rc) if rc is not None else None,
    )


def validate_version_syntax(version: str) -> None:
    parse_release_version(version)


def python_package_version(version: str) -> str:
    return parse_release_version(version).python_package


def prepare_release(root: Path, version: str) -> None:
    """Update the project and its lock entry after validating both inputs."""
    package_version = python_package_version(version)
    manifest_path, lock_path = root / "pyproject.toml", root / "uv.lock"
    manifest, lock = manifest_path.read_text(), lock_path.read_text()
    project = tomllib.loads(manifest)["project"]
    packages = [item for item in tomllib.loads(lock)["package"] if item["name"] == "ohkit"]
    if project["name"] != "ohkit" or len(packages) != 1:
        raise ReleaseVersionError("Expected one ohkit project and lock entry")
    if project["version"] != "0.0.0" or packages[0]["version"] != "0.0.0":
        raise ReleaseVersionError("Release preparation requires source version 0.0.0")
    manifest, manifest_count = re.subn(
        r'(?ms)(^\[project\]\n(?:(?!^\[).)*?^version = )"0\.0\.0"',
        rf'\g<1>"{package_version}"',
        manifest,
    )
    lock, lock_count = re.subn(
        r'(?m)(^name = "ohkit"\nversion = )"0\.0\.0"',
        rf'\g<1>"{package_version}"',
        lock,
    )
    if manifest_count != 1 or lock_count != 1:
        raise ReleaseVersionError("Cannot locate unique source version fields")
    manifest_path.write_text(manifest)
    lock_path.write_text(lock)
