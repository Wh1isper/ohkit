from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow(name):
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())


def test_release_trust_and_artifact_boundary():
    release = workflow("release-ohkit.yml")
    # PyYAML's YAML 1.1 loader interprets the GitHub Actions `on` key as True.
    assert release[True] == {"push": {"tags": ["release/ohkit-v*"]}}
    assert release["permissions"] == {"contents": "read"}
    jobs = release["jobs"]
    assert "environment" not in jobs["build"]
    assert jobs["publish"]["environment"] == "ohkit-pypi"
    assert jobs["publish"]["needs"] == "build"
    assert jobs["create-release"]["needs"] == ["build", "publish"]
    assert not any("checkout" in step.get("uses", "") for step in jobs["publish"]["steps"])
    publish = jobs["publish"]["steps"][-1]
    assert publish["env"]["UV_PUBLISH_TOKEN"] == "${{ secrets.PYPI_TOKEN }}"
    assert publish["run"] == "uv publish --check-url https://pypi.org/simple/ dist/*"
    text = (ROOT / ".github/workflows/release-ohkit.yml").read_text()
    assert "dist/ohkit-${python_version}" in text
    assert "a13n" not in text


def test_privileged_pr_automation_only_loads_base_code():
    overview = workflow("pr-change-breakdown.yml")
    checkout = overview["jobs"]["breakdown"]["steps"][0]
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert checkout["with"]["persist-credentials"] is False
    labels = workflow("pr-labels.yml")
    assert not any("checkout" in step.get("uses", "") for job in labels["jobs"].values() for step in job["steps"])
