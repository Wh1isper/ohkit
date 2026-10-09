"""Reproducible Codex wire models and native upstream regression checks.

Only this development tool knows schema locations and generation options. The
installed package neither downloads Codex nor generates code at import time.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "protocol/codex"
MODELS = ROOT / "ohkit/backends/codex/_generated.py"
VERSION_FILE = ROOT / "ohkit/backends/codex/_version.py"
ARCHIVE = "codex-x86_64-unknown-linux-musl.tar.gz"
EXECUTABLE = "codex-x86_64-unknown-linux-musl"
API = "https://api.github.com/repos/openai/codex/releases"
NOTICES = ROOT / "third-party/codex"


class SurfaceChanged(ValueError):
    """Upstream no longer exports our selected method/type surface."""


# This is the supported adapter surface, not a second definition of its fields.
CALLS = {
    "initialize": ("InitializeParams", "InitializeResponse"),
    "environment/add": ("EnvironmentAddParams", "EnvironmentAddResponse"),
    "environment/status": ("EnvironmentStatusParams", "EnvironmentStatusResponse"),
    "thread/start": ("ThreadStartParams", "ThreadStartResponse"),
    "thread/resume": ("ThreadResumeParams", "ThreadResumeResponse"),
    "thread/fork": ("ThreadForkParams", "ThreadForkResponse"),
    "turn/start": ("TurnStartParams", "TurnStartResponse"),
    "turn/steer": ("TurnSteerParams", "TurnSteerResponse"),
    "turn/interrupt": ("TurnInterruptParams", "TurnInterruptResponse"),
}
NOTIFICATIONS = {
    "turn/started": "TurnStartedNotification",
    "turn/completed": "TurnCompletedNotification",
    "item/started": "ItemStartedNotification",
    "item/completed": "ItemCompletedNotification",
    "item/agentMessage/delta": "AgentMessageDeltaNotification",
    "item/reasoning/summaryTextDelta": "ReasoningSummaryTextDeltaNotification",
    "item/reasoning/textDelta": "ReasoningTextDeltaNotification",
    "item/commandExecution/outputDelta": "CommandExecutionOutputDeltaNotification",
    "thread/tokenUsage/updated": "ThreadTokenUsageUpdatedNotification",
    "serverRequest/resolved": "ServerRequestResolvedNotification",
}
REQUESTS = {
    "item/commandExecution/requestApproval": (
        "CommandExecutionRequestApprovalParams",
        "CommandExecutionRequestApprovalResponse",
    ),
    "item/fileChange/requestApproval": ("FileChangeRequestApprovalParams", "FileChangeRequestApprovalResponse"),
    "item/permissions/requestApproval": ("PermissionsRequestApprovalParams", "PermissionsRequestApprovalResponse"),
    "item/tool/requestUserInput": ("ToolRequestUserInputParams", "ToolRequestUserInputResponse"),
}


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release(version: str | None = None) -> dict:
    path = "/latest" if version is None else f"/tags/rust-v{version}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ohkit-protocol-maintenance"}
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(API + path, headers=headers), timeout=60) as response:
        result = json.load(response)
    if result.get("draft") or result.get("prerelease") or not re.fullmatch(r"rust-v\d+\.\d+\.\d+", result["tag_name"]):
        raise ValueError("Expected a stable Codex release")
    return result


def asset_metadata(info: dict) -> dict:
    asset = next(a for a in info["assets"] if a["name"] == ARCHIVE)
    checksum = asset.get("digest", "")
    if not isinstance(checksum, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", checksum):
        raise ValueError("Release asset has no SHA-256 digest; cannot verify the download")
    return {"version": info["tag_name"].removeprefix("rust-v"), "archive_sha256": checksum[7:]}


def download_binary(metadata: dict, directory: Path) -> Path:
    archive = directory / ARCHIVE
    url = f"https://github.com/openai/codex/releases/download/rust-v{metadata['version']}/{ARCHIVE}"
    with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    if digest(archive.read_bytes()) != metadata["archive_sha256"]:
        raise ValueError("Codex archive checksum mismatch")
    with tarfile.open(archive) as contents:
        member = contents.getmember(EXECUTABLE)
        contents.extract(member, directory, filter="data")
    return directory / EXECUTABLE


def collect_schema(directory: Path) -> dict:
    """Merge self-contained official schemas without changing field semantics."""
    names = set(NOTIFICATIONS.values())
    for pair in (*CALLS.values(), *REQUESTS.values()):
        names.update(pair)
    definitions: dict = {}
    for name in sorted(names):
        candidates = list(directory.rglob(name + ".json"))
        # Prefer v2 where a legacy type has the same name.
        path = directory / "v2" / (name + ".json")
        if not path.exists():
            if len(candidates) != 1:
                raise SurfaceChanged(f"Ambiguous or missing upstream schema: {name}")
            path = candidates[0]
        schema = json.loads(path.read_text())
        children = schema.pop("definitions", {})
        schema.pop("$schema", None)
        children[name] = schema
        for key, value in children.items():
            if key in definitions and definitions[key] != value:
                raise SurfaceChanged(f"Conflicting upstream definitions: {key}")
            definitions[key] = value
    # Check method/params association independently of our selected type names.
    for filename, methods in (
        ("ClientRequest", CALLS),
        ("ServerRequest", REQUESTS),
        ("ServerNotification", NOTIFICATIONS),
    ):
        envelope = json.loads((directory / (filename + ".json")).read_text())
        variants = {v["properties"]["method"]["enum"][0]: v for v in envelope["oneOf"]}
        for method, shape in methods.items():
            name = shape[0] if isinstance(shape, tuple) else shape
            if method not in variants:
                raise SurfaceChanged(f"Upstream method removed: {method}")
            ref = variants[method]["properties"].get("params", {}).get("$ref")
            if not isinstance(ref, str) or ref.rsplit("/", 1)[-1] != name:
                raise SurfaceChanged(f"Upstream method shape changed: {method}")
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "CodexProtocol",
        "type": "object",
        "definitions": definitions,
    }


def export_schema(binary: Path, version: str, directory: Path) -> dict:
    actual = subprocess.check_output([str(binary), "--version"], text=True, timeout=10).strip()
    if actual != f"codex-cli {version}":
        raise ValueError(f"Expected Codex {version}, found {actual}")
    subprocess.run(
        [str(binary), "app-server", "generate-json-schema", "--experimental", "--out", str(directory)],
        check=True,
        timeout=60,
    )
    return collect_schema(directory)


def generate(schema_path: Path, output: Path, version: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(schema_path),
            "--input-file-type",
            "jsonschema",
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--output",
            str(output),
            "--target-python-version",
            "3.13",
            "--snake-case-field",
            "--use-annotated",
            "--field-constraints",
            "--enum-field-as-literal",
            "all",
            "--use-union-operator",
            "--use-standard-collections",
            "--disable-timestamp",
            "--use-title-as-name",
            "--collapse-root-models",
            "--strict-nullable",
            "--base-class",
            "ohkit.backends.codex._wire.WireModel",
            "--strict-refs",
            "--formatters",
            "ruff-check",
            "ruff-format",
            "--custom-file-header",
            f"# Generated from OpenAI Codex rust-v{version} (Apache-2.0).\n# Do not edit; run make codex-generate. See THIRD_PARTY_NOTICES.md.",
        ],
        check=True,
        cwd=ROOT,
    )
    # Temporary paths otherwise lose first-party imports and per-file rules.
    linted = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--fix",
            "--config",
            str(ROOT / "pyproject.toml"),
            "--stdin-filename",
            str(MODELS),
            "-",
        ],
        input=output.read_text(),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    output.write_text(linted.stdout)
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--config", str(ROOT / "pyproject.toml"), str(output)],
        check=True,
        cwd=ROOT,
    )


def check_generated(check: bool) -> None:
    metadata = json.loads((SOURCE / "manifest.json").read_text())
    schema_path = SOURCE / "schema.json"
    if digest(schema_path.read_bytes()) != metadata["schema_sha256"]:
        raise ValueError("Schema snapshot checksum mismatch; use the update command")
    version_text = version_source(metadata["version"])
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "_generated.py"
        generate(schema_path, output, metadata["version"])
        for target, text in ((MODELS, output.read_text()), (VERSION_FILE, version_text)):
            if check:
                if not target.exists() or target.read_text() != text:
                    raise ValueError(f"Generated file is stale: {target.relative_to(ROOT)}; run make codex-generate")
            else:
                target.write_text(text)


def version_source(version: str) -> str:
    return f'"""Generated native compatibility baseline; do not edit."""\n\nCODEX_VERSION = "{version}"\n'


def upstream_notices(version: str) -> dict[str, bytes]:
    result = {}
    for name in ("LICENSE", "NOTICE"):
        url = f"https://raw.githubusercontent.com/openai/codex/rust-v{version}/{name}"
        with urllib.request.urlopen(url, timeout=60) as response:
            result[name] = response.read()
    return result


def update(version: str, binary: Path | None) -> None:
    metadata = asset_metadata(release(version))
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        executable = binary.resolve() if binary else download_binary(metadata, directory)
        schema = export_schema(executable, version, directory / "schemas")
        text = canonical(schema)
        metadata["schema_sha256"] = digest(text.encode())
        snapshot = directory / "schema.json"
        snapshot.write_text(text)
        generated = directory / "_generated.py"
        generate(snapshot, generated, version)
        notices = upstream_notices(version)
        # Prepare everything before touching the baseline; failed downloads or
        # generation leave the checked-in compatibility contract unchanged.
        SOURCE.mkdir(parents=True, exist_ok=True)
        NOTICES.mkdir(parents=True, exist_ok=True)
        (SOURCE / "schema.json").write_text(text)
        (SOURCE / "manifest.json").write_text(canonical(metadata))
        MODELS.write_bytes(generated.read_bytes())
        VERSION_FILE.write_text(version_source(version))
        for name, content in notices.items():
            (NOTICES / name).write_bytes(content)


def upstream_report(baseline: dict, current: dict, old: dict, new: dict) -> str:
    before, after = old["definitions"], new["definitions"]
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    lines = [
        "## Schema review",
        "",
        f"- Selected definitions: {len(added)} added, {len(removed)} removed, {len(changed)} changed.",
        "",
        "Version/schema differences are informational. Only native test outcomes determine the regression status.",
        "",
    ]
    for title, names in (("Added", added), ("Removed", removed), ("Changed", changed)):
        if names:
            lines.extend([f"## {title}", "", *[f"- `{name}`" for name in names], ""])
    lines.extend(
        [
            "## Upgrade",
            "",
            f"Run `uv run python scripts/codex_protocol.py update --version {current['version']}`, review the generated diff, and run `make check-all codex-native-test` before accepting the new baseline.",
            "",
        ]
    )
    return "\n".join(lines)


@dataclass(frozen=True)
class NativeResult:
    status: Literal["passed", "failed", "inconclusive"]
    cases: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    detail: str = ""


def native_result(path: Path, returncode: int) -> NativeResult:
    """Require a complete, non-skipped pytest suite, not merely exit zero."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        return NativeResult("inconclusive", detail=f"Missing or invalid JUnit report: {error}")
    tests = root.findall(".//testcase")
    cases = tuple(sorted(f"{case.get('classname')}::{case.get('name')}" for case in tests))
    failures = tuple(
        sorted(f"{case.get('classname')}::{case.get('name')}" for case in tests if case.find("failure") is not None)
    )
    if not cases or len(set(cases)) != len(cases) or root.findall(".//error") or root.findall(".//skipped"):
        return NativeResult("inconclusive", cases, failures, "Empty, skipped, duplicate, or errored test cases")
    if returncode == 0 and not failures:
        return NativeResult("passed", cases)
    if returncode == 1 and failures:
        return NativeResult("failed", cases, failures)
    return NativeResult("inconclusive", cases, failures, f"Unexpected pytest exit {returncode}")


def run_native(binary: Path, version: str, output: Path) -> NativeResult:
    """Run unchanged repository code with a verified executable on Linux CI."""
    output.mkdir(parents=True, exist_ok=True)
    junit = output / "junit.xml"
    junit.unlink(missing_ok=True)
    env = dict(os.environ)
    env.update(OHKIT_TEST_NATIVE="1", OHKIT_CODEX_BINARY=str(binary.resolve()), OHKIT_CODEX_TEST_VERSION=version)
    # Ambient pytest selection flags must not turn partial coverage into green.
    env.pop("PYTEST_ADDOPTS", None)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_codex_native.py",
        "-q",
        "-o",
        "addopts=--import-mode=importlib",
        # The suite deadline owns timeout classification; pytest-timeout's
        # per-test pytest.fail() would otherwise look like a native regression.
        "--timeout=0",
        f"--junitxml={junit}",
    ]
    with (output / "pytest.log").open("w") as log:
        with subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log, start_new_session=True) as process:
            try:
                returncode = process.wait(timeout=300)
            except subprocess.TimeoutExpired:
                # The native servers are descendants; killing pytest alone leaks them.
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                return NativeResult("inconclusive", detail="Native suite exceeded 300s; process group terminated")
    return native_result(junit, returncode)


def regression_status(baseline: NativeResult, candidate: NativeResult) -> int:
    if baseline.status != "passed" or candidate.status == "inconclusive" or baseline.cases != candidate.cases:
        return 2
    return 1 if candidate.status == "failed" else 0


def check_upstream(output: Path) -> int:
    """Return 0 for covered paths passing, 1 for regression, 2 for inconclusive."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Clear only our artifacts, never arbitrary caller-owned output contents.
    for name in (
        "report.md",
        "result.json",
        "schema.diff",
        "schema.json",
        "baseline/pytest.log",
        "baseline/junit.xml",
        "candidate/pytest.log",
        "candidate/junit.xml",
    ):
        (output / name).unlink(missing_ok=True)
    baseline: dict = {}
    current: dict = {}
    reference = candidate = NativeResult("inconclusive", detail="Not run")
    schema_status = "unavailable"
    report = "# Codex protocol maintenance\n\n"
    status = 2
    try:
        if sys.platform != "linux" or platform.machine() != "x86_64":
            raise ValueError("Upstream regression checks require Linux x86_64; use native tests on other platforms")
        baseline = json.loads((SOURCE / "manifest.json").read_text())
        current = asset_metadata(release())
        report += f"- Tested baseline: `{baseline['version']}`\n- Latest stable release: `{current['version']}`\n\n"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            reference_dir = directory / "baseline"
            reference_dir.mkdir()
            reference_binary = download_binary(baseline, reference_dir)
            reference = run_native(reference_binary, baseline["version"], output / "baseline")
            if baseline["version"] == current["version"] and baseline["archive_sha256"] == current["archive_sha256"]:
                binary = reference_binary
                candidate = reference
                report += "Latest and baseline are the same verified asset; the native result is reused.\n\n"
            else:
                candidate_dir = directory / "candidate"
                candidate_dir.mkdir()
                binary = download_binary(current, candidate_dir)
                candidate = run_native(binary, current["version"], output / "candidate")
            status = regression_status(reference, candidate)
            # Schema extraction is supplementary evidence, never a test oracle.
            try:
                old = json.loads((SOURCE / "schema.json").read_text())
                new = export_schema(binary, current["version"], directory / "schemas")
                schema_status = "unchanged" if old == new else "changed"
                report += upstream_report(baseline, current, old, new)
                (output / "schema.diff").write_text(
                    "".join(
                        difflib.unified_diff(
                            canonical(old).splitlines(True),
                            canonical(new).splitlines(True),
                            fromfile=baseline["version"],
                            tofile=current["version"],
                        )
                    )
                )
                (output / "schema.json").write_text(canonical(new))
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                report += f"Schema comparison unavailable: {type(error).__name__}: {error}\n\n"
    except (OSError, ValueError, KeyError, StopIteration, tarfile.TarError, subprocess.SubprocessError) as error:
        status = 2
        report += f"Check could not complete: {type(error).__name__}: {error}\n\n"
    state = ("passed", "regression", "inconclusive")[status]
    report += (
        f"\n## Native regression check\n\nStatus: **{state}** (exit {status}).\n\n"
        f"- Baseline: **{reference.status}**, {len(reference.cases)} cases. {reference.detail}\n"
        f"- Candidate: **{candidate.status}**, {len(candidate.cases)} cases. {candidate.detail}\n"
        f"- Schema: **{schema_status}** (informational only).\n\n"
        "The same unmodified adapter and test suite run against both executables; models are not regenerated. "
        "Passing covers only these deterministic native scenarios, not every protocol variant or live provider. "
        "A regression means candidate test failures with a passing baseline and matching case coverage; "
        "inspect pytest logs/JUnit before attributing the cause. Inconclusive is a check failure, not a compatibility verdict.\n"
    )
    (output / "report.md").write_text(report)
    (output / "result.json").write_text(
        canonical(
            {
                "status": state,
                "baseline": baseline.get("version"),
                "latest": current.get("version"),
                "schema": schema_status,
                "native": {"baseline": asdict(reference), "candidate": asdict(candidate)},
            }
        )
    )
    print(report)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a") as stream:
            stream.write(report)
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate").add_argument("--check", action="store_true")
    refresh = commands.add_parser("update")
    refresh.add_argument("--version", required=True)
    refresh.add_argument("--binary", type=Path)
    upstream = commands.add_parser("check-upstream")
    upstream.add_argument("--output", type=Path, default=ROOT / "test-results/codex-upstream")
    args = parser.parse_args()
    if args.command == "generate":
        check_generated(args.check)
    elif args.command == "update":
        if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
            parser.error("--version must be a stable X.Y.Z version")
        update(args.version, args.binary)
    else:
        raise SystemExit(check_upstream(args.output))


if __name__ == "__main__":
    main()
