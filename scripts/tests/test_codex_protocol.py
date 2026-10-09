"""Maintenance tests are offline; native export is covered by the opt-in suite."""

import io
import json
import subprocess
import tarfile
from pathlib import Path

import codex_protocol as protocol
import pytest


def write_json(path, value):
    path.write_text(protocol.canonical(value))


def baseline(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(protocol, "SOURCE", source)
    write_json(source / "manifest.json", {"version": "1.0.0", "archive_sha256": "baseline", "schema_sha256": "unused"})
    old = {"definitions": {"Old": {"type": "string"}}}
    write_json(source / "schema.json", old)
    return source, old


def test_collect_schema_uses_v2_and_checks_method_association(monkeypatch, tmp_path):
    monkeypatch.setattr(protocol, "CALLS", {"test": ("Params", "Response")})
    monkeypatch.setattr(protocol, "REQUESTS", {})
    monkeypatch.setattr(protocol, "NOTIFICATIONS", {})
    v2 = tmp_path / "v2"
    v2.mkdir()
    shape = {"type": "object", "properties": {"field": {"type": ["string", "null"]}}, "required": ["field"]}
    write_json(v2 / "Params.json", shape)
    write_json(tmp_path / "Params.json", {"type": "string"})
    write_json(v2 / "Response.json", {"type": "object"})
    envelope = {"oneOf": [{"properties": {"method": {"enum": ["test"]}, "params": {"$ref": "#/definitions/Params"}}}]}
    write_json(tmp_path / "ClientRequest.json", envelope)
    for name in ("ServerRequest", "ServerNotification"):
        write_json(tmp_path / f"{name}.json", {"oneOf": []})
    assert protocol.collect_schema(tmp_path)["definitions"]["Params"] == shape
    envelope["oneOf"][0]["properties"]["params"]["$ref"] = "#/definitions/Other"
    write_json(tmp_path / "ClientRequest.json", envelope)
    with pytest.raises(protocol.SurfaceChanged, match="shape changed"):
        protocol.collect_schema(tmp_path)
    write_json(tmp_path / "ClientRequest.json", {"oneOf": []})
    with pytest.raises(protocol.SurfaceChanged, match="method removed"):
        protocol.collect_schema(tmp_path)
    write_json(v2 / "Response.json", {"definitions": {"Params": {"type": "boolean"}}})
    with pytest.raises(protocol.SurfaceChanged, match="Conflicting"):
        protocol.collect_schema(tmp_path)


def test_asset_requires_official_checksum():
    release = {"tag_name": "rust-v1.2.3", "assets": [{"name": protocol.ARCHIVE, "digest": "sha256:" + "a" * 64}]}
    assert protocol.asset_metadata(release) == {"version": "1.2.3", "archive_sha256": "a" * 64}
    release["assets"][0]["digest"] = None
    with pytest.raises((ValueError, TypeError)):
        protocol.asset_metadata(release)


def test_download_verifies_checksum_before_extraction(monkeypatch, tmp_path):
    content = io.BytesIO()
    with tarfile.open(fileobj=content, mode="w:gz") as archive:
        member = tarfile.TarInfo(protocol.EXECUTABLE)
        member.size = 4
        member.mode = 0o755
        archive.addfile(member, io.BytesIO(b"test"))
    data = content.getvalue()
    monkeypatch.setattr(protocol.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(data))
    metadata = {"version": "1.2.3", "archive_sha256": "wrong"}
    with pytest.raises(ValueError, match="checksum mismatch"):
        protocol.download_binary(metadata, tmp_path)
    assert not (tmp_path / protocol.EXECUTABLE).exists()
    metadata["archive_sha256"] = protocol.digest(data)
    assert protocol.download_binary(metadata, tmp_path).read_bytes() == b"test"


def test_release_rejects_nonstable_tags(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    seen = []

    def response(request, **kwargs):
        seen.append(request.full_url)
        return io.BytesIO(b'{"tag_name":"rust-v1.2.3-alpha.1","prerelease":true}')

    monkeypatch.setattr(protocol.urllib.request, "urlopen", response)
    with pytest.raises(ValueError, match="stable Codex"):
        protocol.release()
    assert seen == [protocol.API + "/latest"]


@pytest.mark.parametrize("version,changed", [("1.0.0", False), ("1.0.1", False), ("1.0.1", True)])
def test_upstream_drift_alone_is_informational(monkeypatch, tmp_path, version, changed):
    _, old = baseline(monkeypatch, tmp_path)
    current = {"version": version, "archive_sha256": "baseline"}
    monkeypatch.setattr(protocol, "release", lambda: {})
    monkeypatch.setattr(protocol, "asset_metadata", lambda value: current)
    monkeypatch.setattr(protocol, "download_binary", lambda *args: Path("codex"))
    calls = []

    def native(binary, version, output):
        calls.append(version)
        return protocol.NativeResult("passed", ("native::test",))

    monkeypatch.setattr(protocol, "run_native", native)
    new = {"definitions": {"New": {"type": "integer"}}} if changed else old
    monkeypatch.setattr(protocol, "export_schema", lambda *args: new)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    output = tmp_path / "report"
    before = {p.name: p.read_bytes() for p in protocol.SOURCE.iterdir()}
    assert protocol.check_upstream(output) == 0
    assert calls == (["1.0.0"] if version == "1.0.0" else ["1.0.0", version])
    assert before == {p.name: p.read_bytes() for p in protocol.SOURCE.iterdir()}
    assert summary.read_text() == (output / "report.md").read_text()
    assert bool((output / "schema.diff").read_text()) == changed
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "passed"
    assert result["schema"] == ("changed" if changed else "unchanged")


@pytest.mark.parametrize("error,status", [(OSError("network unavailable"), 2), (ValueError("checksum mismatch"), 2)])
def test_failed_check_keeps_diagnostic_not_stale_diff(monkeypatch, tmp_path, error, status):
    baseline(monkeypatch, tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    def fail():
        raise error

    monkeypatch.setattr(protocol, "release", fail)
    output = tmp_path / "report"
    output.mkdir()
    (output / "schema.diff").write_text("stale")
    assert protocol.check_upstream(output) == status
    assert str(error) in (output / "report.md").read_text()
    assert not (output / "schema.diff").exists()


def test_generate_checks_integrity_and_stale_output(monkeypatch, tmp_path):
    source, _ = baseline(monkeypatch, tmp_path)
    models, version = tmp_path / "models.py", tmp_path / "version.py"
    monkeypatch.setattr(protocol, "MODELS", models)
    monkeypatch.setattr(protocol, "VERSION_FILE", version)
    monkeypatch.setattr(protocol, "ROOT", tmp_path)
    monkeypatch.setattr(protocol, "generate", lambda schema, output, version: output.write_text("generated\n"))
    with pytest.raises(ValueError, match="checksum"):
        protocol.check_generated(False)
    write_json(
        source / "manifest.json",
        {
            "version": "1.0.0",
            "schema_sha256": protocol.digest((source / "schema.json").read_bytes()),
        },
    )
    protocol.check_generated(False)
    protocol.check_generated(True)
    assert version.read_text() == protocol.version_source("1.0.0")
    models.write_text("stale\n")
    with pytest.raises(ValueError, match="stale"):
        protocol.check_generated(True)


def test_update_does_not_publish_snapshot_when_generation_fails(monkeypatch, tmp_path):
    source, old = baseline(monkeypatch, tmp_path)
    before = (source / "manifest.json").read_bytes()
    monkeypatch.setattr(protocol, "release", lambda version: {})
    monkeypatch.setattr(protocol, "asset_metadata", lambda value: {"version": "2.0.0"})
    monkeypatch.setattr(protocol, "export_schema", lambda *args: {"definitions": {}})

    def fail(*args):
        raise subprocess.CalledProcessError(1, "generate")

    monkeypatch.setattr(protocol, "generate", fail)
    with pytest.raises(subprocess.CalledProcessError):
        protocol.update("2.0.0", Path("codex"))
    assert (source / "manifest.json").read_bytes() == before
    assert json.loads((source / "schema.json").read_text()) == old


@pytest.mark.parametrize(
    "reference,candidate,expected",
    [
        ("passed", "passed", 0),
        ("passed", "failed", 1),
        ("failed", "failed", 2),
        ("failed", "passed", 2),
        ("inconclusive", "failed", 2),
        ("passed", "inconclusive", 2),
    ],
)
def test_upstream_verdict_requires_healthy_control(monkeypatch, tmp_path, reference, candidate, expected):
    _, old = baseline(monkeypatch, tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(protocol, "release", lambda: {})
    monkeypatch.setattr(protocol, "asset_metadata", lambda value: {"version": "2.0.0", "archive_sha256": "new"})
    monkeypatch.setattr(protocol, "download_binary", lambda *args: Path("codex"))
    monkeypatch.setattr(protocol, "export_schema", lambda *args: old)
    monkeypatch.setattr(
        protocol,
        "run_native",
        lambda binary, version, output: protocol.NativeResult(
            reference if version == "1.0.0" else candidate, ("native::test",)
        ),
    )
    output = tmp_path / "report"
    assert protocol.check_upstream(output) == expected
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == ("passed", "regression", "inconclusive")[expected]


def test_mismatched_coverage_cannot_pass_or_report_regression():
    reference = protocol.NativeResult("passed", ("a", "b"))
    for status in ("passed", "failed"):
        assert protocol.regression_status(reference, protocol.NativeResult(status, ("a",))) == 2


@pytest.mark.parametrize("error", [protocol.SurfaceChanged("missing Params"), OSError("export failed")])
def test_schema_export_failure_does_not_override_native_evidence(monkeypatch, tmp_path, error):
    baseline(monkeypatch, tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(protocol, "release", lambda: {})
    monkeypatch.setattr(protocol, "asset_metadata", lambda value: {"version": "2.0.0", "archive_sha256": "new"})
    monkeypatch.setattr(protocol, "download_binary", lambda *args: Path("codex"))
    monkeypatch.setattr(protocol, "run_native", lambda *args: protocol.NativeResult("passed", ("a",)))

    def fail(*args):
        raise error

    monkeypatch.setattr(protocol, "export_schema", fail)
    output = tmp_path / "report"
    assert protocol.check_upstream(output) == 0
    result = json.loads((output / "result.json").read_text())
    assert result["schema"] == "unavailable"
    assert str(error) in (output / "report.md").read_text()


@pytest.mark.parametrize(
    "cases,code,status",
    [
        ('<testcase classname="native" name="a"/>', 0, "passed"),
        ('<testcase classname="native" name="a"><failure/></testcase>', 1, "failed"),
        ('<testcase classname="native" name="a"><error/></testcase>', 1, "inconclusive"),
        ('<testcase classname="native" name="a"><skipped/></testcase>', 0, "inconclusive"),
        ('<testcase classname="native" name="a"><failure/><error/></testcase>', 1, "inconclusive"),
        ('<testcase classname="native" name="a"/>', 2, "inconclusive"),
        ('<testcase classname="native" name="a"><failure/></testcase>', 0, "inconclusive"),
        ("", 0, "inconclusive"),
        ("", 5, "inconclusive"),
    ],
)
def test_native_junit_classification(tmp_path, cases, code, status):
    path = tmp_path / "junit.xml"
    path.write_text(f"<testsuites><testsuite>{cases}</testsuite></testsuites>")
    result = protocol.native_result(path, code)
    assert result.status == status
    if status == "failed":
        assert result.failures == ("native::a",)


def test_native_missing_or_malformed_report_is_inconclusive(tmp_path):
    path = tmp_path / "junit.xml"
    assert protocol.native_result(path, 0).status == "inconclusive"
    path.write_text("not XML")
    assert protocol.native_result(path, 0).status == "inconclusive"


def test_native_runner_selects_candidate_without_regeneration(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    process = MagicMock()
    process.__enter__.return_value = process
    process.wait.return_value = 0
    seen = []

    def launch(command, **kwargs):
        seen.append((command, kwargs))
        report = next(arg.split("=", 1)[1] for arg in command if arg.startswith("--junitxml="))
        Path(report).write_text(
            '<testsuites><testsuite><testcase classname="native" name="a"/></testsuite></testsuites>'
        )
        return process

    monkeypatch.setenv("PYTEST_ADDOPTS", "-k nonexistent")
    monkeypatch.setattr(protocol.subprocess, "Popen", launch)
    assert protocol.run_native(Path("codex"), "9.0.0", tmp_path).status == "passed"
    command, kwargs = seen[0]
    assert command[1:4] == ["-m", "pytest", "tests/test_codex_native.py"]
    assert "addopts=--import-mode=importlib" in command
    assert "--timeout=0" in command
    assert kwargs["cwd"] == protocol.ROOT
    assert kwargs["env"]["OHKIT_CODEX_TEST_VERSION"] == "9.0.0"
    assert kwargs["env"]["OHKIT_TEST_NATIVE"] == "1"
    assert kwargs["env"]["OHKIT_CODEX_BINARY"] == str(Path("codex").resolve())
    assert "PYTEST_ADDOPTS" not in kwargs["env"]
    assert kwargs["start_new_session"] is True


def test_native_timeout_kills_native_descendants_and_cannot_pass(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    process = MagicMock()
    process.__enter__.return_value = process
    process.wait.side_effect = [subprocess.TimeoutExpired("pytest", 300), -9]
    monkeypatch.setattr(protocol.subprocess, "Popen", lambda *args, **kwargs: process)
    killed = []
    monkeypatch.setattr(protocol.os, "killpg", lambda pid, sig: killed.append((pid, sig)))
    result = protocol.run_native(Path("codex"), "1.0.0", tmp_path)
    assert result.status == "inconclusive"
    assert killed == [(process.pid, protocol.signal.SIGKILL)]
    assert "300s" in result.detail
