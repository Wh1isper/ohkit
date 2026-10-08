import tomllib

import pytest
from release_notes import ReleaseChange, build_release_command, previous_release_tag, render_release_notes
from release_version import parse_release_version, prepare_release


@pytest.mark.parametrize(("version", "expected"), [("1.2.3", "1.2.3"), ("0.1.0-rc.1", "0.1.0rc1")])
def test_release_version(version, expected):
    assert parse_release_version(version).python_package == expected


@pytest.mark.parametrize(
    "version", ["v1.0.0", "01.0.0", "1.0", "1.0.0rc1", "1.0.0-rc.0", "1.0.0-rc.01", "1.0.0\n", "1.0.0+local"]
)
def test_invalid_release_versions(version):
    with pytest.raises(ValueError):
        parse_release_version(version)


@pytest.mark.parametrize("version", ["1.2.3", "1.2.3-rc.2"])
def test_prepare_manifest_and_lock(tmp_path, version):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ohkit"\nversion = "0.0.0"\n[build-system]\nrequires = []\n'
    )
    (tmp_path / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "ohkit"\nversion = "0.0.0"\n[[package]]\nname = "other"\nversion = "1.0.0"\n'
    )
    prepare_release(tmp_path, version)
    assert (
        tomllib.loads((tmp_path / "pyproject.toml").read_text())["project"]["version"]
        == parse_release_version(version).python_package
    )
    packages = tomllib.loads((tmp_path / "uv.lock").read_text())["package"]
    assert packages[0]["version"] == parse_release_version(version).python_package
    assert packages[1]["version"] == "1.0.0"
    with pytest.raises(ValueError):
        prepare_release(tmp_path, version)


def test_invalid_lock_does_not_modify_manifest(tmp_path):
    manifest = '[project]\nname = "ohkit"\nversion = "0.0.0"\n'
    (tmp_path / "pyproject.toml").write_text(manifest)
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "ohkit"\nversion = "1.0.0"\n')
    with pytest.raises(ValueError):
        prepare_release(tmp_path, "2.0.0")
    assert (tmp_path / "pyproject.toml").read_text() == manifest


def test_stable_and_rc_note_bases():
    tags = ["release/ohkit-v0.1.0", "release/ohkit-v0.2.0-rc.1", "release/ohkit-v0.2.0-rc.2", "release/other-v9.0.0"]
    assert previous_release_tag("ohkit", "0.2.0", tags) == tags[0]
    assert previous_release_tag("ohkit", "0.2.0-rc.3", tags) == tags[2]
    assert previous_release_tag("ohkit", "0.3.0-rc.1", tags) == tags[0]


def test_notes_filter_labels_and_escape_titles():
    notes = render_release_notes(
        component="ohkit",
        version="0.2.0",
        repository="o/r",
        previous_tag="release/ohkit-v0.1.0",
        changes=[
            ReleaseChange("abc123456", "feat(api): support <agent> (#1)", labels=("enhancement",)),
            ReleaseChange("def123456", "chore(ci): hidden (#2)", labels=("chore",)),
        ],
    )
    assert "Features" in notes and "\\<agent\\>" in notes
    assert "hidden" not in notes
    assert "/pull/1" in notes


def test_first_release_is_honest_and_rc_marked():
    notes = render_release_notes(component="ohkit", version="0.1.0-rc.1", repository="o/r", previous_tag=None)
    assert "does not yet include agent backends" in notes
    command = build_release_command(component="ohkit", version="0.1.0-rc.1", repository="o/r", title="ohkit", assets=[])
    assert "--prerelease" in command and "--verify-tag" in command
