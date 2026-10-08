from urllib.error import HTTPError

import pytest
from create_docs_project import cloudflare_request, ensure_project

PROJECT = {"name": "ohkit-docs", "production_branch": "main", "subdomain": "ohkit-docs.pages.dev", "source": None}


def test_existing_project_is_verified_without_writing():
    calls = []

    def request(method, path, payload):
        calls.append((method, path, payload))
        return {"result": [PROJECT] if path.startswith("?") else PROJECT}

    result = ensure_project(request)
    assert result["created"] is False
    assert result["has_production_deployment"] is False
    assert [call[0] for call in calls] == ["GET", "GET"]


def test_creation_follows_all_list_pages_and_reads_back():
    calls = []

    def request(method, path, payload):
        calls.append((method, path, payload))
        if path.startswith("?page=1&"):
            return {"result": [{"name": "another-project"}]}
        if path.startswith("?page=2&"):
            return {"result": []}
        return {"result": PROJECT}

    result = ensure_project(request)
    assert result["created"] is True
    assert calls == [
        ("GET", "?page=1&per_page=100", None),
        ("GET", "?page=2&per_page=100", None),
        ("POST", "", {"name": "ohkit-docs", "production_branch": "main"}),
        ("GET", "/ohkit-docs", None),
    ]


@pytest.mark.parametrize("override", [{"production_branch": "other"}, {"source": {"type": "github"}}])
def test_mismatched_existing_project_is_not_modified(override):
    calls = []
    project = PROJECT | override

    def request(method, path, payload):
        calls.append(method)
        return {"result": [project] if path.startswith("?") else project}

    with pytest.raises(ValueError, match="does not match"):
        ensure_project(request)
    assert calls == ["GET", "GET"]


def test_uncertain_create_is_not_retried():
    calls = []

    def request(method, path, payload):
        calls.append(method)
        if method == "POST":
            raise RuntimeError("outcome unknown")
        return {"result": []}

    with pytest.raises(RuntimeError, match="unknown"):
        ensure_project(request)
    assert calls == ["GET", "POST"]


def test_list_failure_is_not_treated_as_missing():
    def request(method, path, payload):
        assert method == "GET"
        raise RuntimeError("permission denied")

    with pytest.raises(RuntimeError, match="permission denied"):
        ensure_project(request)


def test_http_error_does_not_expose_credentials(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "private-token")

    def reject(request, timeout):
        assert request.get_header("Authorization") == "Bearer private-token"
        assert timeout == 30
        raise HTTPError(request.full_url, 403, "private-token", {}, None)

    monkeypatch.setattr("create_docs_project.urlopen", reject)
    with pytest.raises(RuntimeError, match="HTTP 403") as error:
        cloudflare_request("GET", "", None)
    assert "private-token" not in str(error.value)
    assert "a" * 32 not in str(error.value)
