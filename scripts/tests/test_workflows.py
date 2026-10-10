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


def test_docs_credentials_require_main_and_explicit_deployment_opt_in():
    docs = workflow("docs.yml")
    assert docs["permissions"] == {"contents": "read"}
    assert "environment" not in docs["jobs"]["build"]
    deploy = docs["jobs"]["deploy"]
    assert deploy["needs"] == "build"
    assert deploy["environment"]["name"] == "docs"
    assert deploy["if"] == (
        "github.event_name == 'push' && github.ref == 'refs/heads/main' && vars.DOCS_DEPLOY_ENABLED == 'true'"
    )
    assert not any("checkout" in step.get("uses", "") for step in deploy["steps"])


def test_docs_project_creation_is_manual_main_only_and_does_not_deploy():
    creation = workflow("create-docs-project.yml")
    assert creation[True] == {"workflow_dispatch": None}
    assert creation["permissions"] == {"contents": "read"}
    job = creation["jobs"]["create"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["environment"] == "docs"
    assert job["steps"][0]["with"]["persist-credentials"] is False
    step = job["steps"][-1]
    assert step["run"] == "python scripts/create_docs_project.py"
    assert step["env"] == {
        "CLOUDFLARE_API_TOKEN": "${{ secrets.CLOUDFLARE_API_TOKEN }}",
        "CLOUDFLARE_ACCOUNT_ID": "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
    }


def test_docs_domain_configuration_is_manual_and_main_only():
    configuration = workflow("configure-docs-domain.yml")
    assert configuration[True] == {"workflow_dispatch": None}
    assert configuration["permissions"] == {"contents": "read"}
    job = configuration["jobs"]["configure"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["environment"] == "docs"
    assert job["steps"][0]["with"]["persist-credentials"] is False
    assert job["steps"][-1]["run"] == "python scripts/configure_docs_domain.py"


def test_codex_maintenance_is_read_only_scheduled_and_preserves_reports():
    maintenance = workflow("codex-upstream.yml")
    assert maintenance[True] == {"schedule": [{"cron": "23 7 * * *"}], "workflow_dispatch": None}
    assert maintenance["permissions"] == {"contents": "read"}
    job = maintenance["jobs"]["check"]
    assert job["timeout-minutes"] == 20
    assert "environment" not in job
    assert job["steps"][0]["with"]["persist-credentials"] is False
    check = next(step for step in job["steps"] if step.get("run") == "make codex-upstream-check")
    assert not check.get("continue-on-error")
    artifact = job["steps"][-1]
    assert artifact["if"] == "always()"
    assert artifact["with"]["path"] == "test-results/codex-upstream/"
    native = workflow("ci.yml")["jobs"]["installed-native"]
    assert any(step.get("run") == "make installed-test" for step in native["steps"])
    assert any(step.get("uses") == "actions/setup-node@v6" for step in native["steps"])
    assert native["steps"][-1]["with"]["path"] == "test-results/installed-native.xml"
    assert "codex-check" in (ROOT / "Makefile").read_text().split("check:", 1)[-1]
