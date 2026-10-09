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
    write_json(source / "manifest.json", {"version": "1.0.0", "schema_sha256": "unused"})
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


@pytest.mark.parametrize("version,changed,status", [("1.0.0", False, 0), ("1.0.1", False, 1), ("1.0.0", True, 1)])
def test_upstream_reports_version_and_schema_drift(monkeypatch, tmp_path, version, changed, status):
    _, old = baseline(monkeypatch, tmp_path)
    current = {"version": version}
    monkeypatch.setattr(protocol, "release", lambda: {})
    monkeypatch.setattr(protocol, "asset_metadata", lambda value: current)
    monkeypatch.setattr(protocol, "download_binary", lambda *args: Path("codex"))
    new = {"definitions": {"New": {"type": "integer"}}} if changed else old
    monkeypatch.setattr(protocol, "export_schema", lambda *args: new)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    output = tmp_path / "report"
    assert protocol.check_upstream(output) == status
    assert summary.read_text() == (output / "report.md").read_text()
    assert bool((output / "schema.diff").read_text()) == changed
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == ("drift" if status else "current")


@pytest.mark.parametrize(
    "error,status", [(OSError("network unavailable"), 2), (protocol.SurfaceChanged("missing Params"), 1)]
)
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
