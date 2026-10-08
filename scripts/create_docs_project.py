"""Create the fixed documentation Pages project without uploading a deployment."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT = "ohkit-docs"
BRANCH = "main"
PAGE_SIZE = 10
APIRequest = Callable[[str, str, dict[str, str] | None], dict[str, Any]]


def cloudflare_request(method: str, path: str, payload: dict[str, str] | None) -> dict[str, Any]:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", account) or not token:
        raise ValueError("Configure CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in the docs Environment")
    request = Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = json.load(response)
    except HTTPError as error:
        # Only numeric API codes are safe diagnostics; never echo remote messages or headers.
        codes: list[int] = []
        try:
            detail = json.load(error)
        except (ValueError, OSError):
            detail = None
        if isinstance(detail, dict) and isinstance(detail.get("errors"), list):
            codes = [
                item["code"]
                for item in detail["errors"]
                if isinstance(item, dict) and isinstance(item.get("code"), int)
            ]
        raise RuntimeError(
            f"Cloudflare {method} failed with HTTP {error.code}, API codes {codes}; "
            "inspect project state before retrying"
        ) from None
    except (URLError, TimeoutError):
        raise RuntimeError(
            f"Cloudflare {method} transport failed; outcome may be unknown, inspect before retrying"
        ) from None
    if not isinstance(body, dict) or body.get("success") is not True:
        raise RuntimeError(f"Cloudflare {method} did not confirm success")
    return body


def find_project(request: APIRequest) -> dict[str, Any] | None:
    page = 1
    while True:
        print(f"Listing Pages projects: page {page}", flush=True)
        response = request("GET", f"?page={page}&per_page={PAGE_SIZE}", None)
        projects = response["result"]
        if not isinstance(projects, list):
            raise ValueError("Cloudflare returned an invalid project list")
        for project in projects:
            if isinstance(project, dict) and project.get("name") == PROJECT:
                return project
        if len(projects) < PAGE_SIZE:
            return None
        page += 1


def ensure_project(request: APIRequest = cloudflare_request) -> dict[str, Any]:
    existing = find_project(request)
    if existing is None:
        # No source configuration means Direct Upload. Never retry this mutation automatically.
        print("Creating ohkit-docs project without a deployment", flush=True)
        request("POST", "", {"name": PROJECT, "production_branch": BRANCH})
    print("Reading back ohkit-docs project", flush=True)
    project = request("GET", f"/{PROJECT}", None)["result"]
    if not isinstance(project, dict):
        raise ValueError("Cloudflare returned invalid project details")
    if (
        project.get("name") != PROJECT
        or project.get("production_branch") != BRANCH
        or project.get("source") is not None
    ):
        raise ValueError("Existing project does not match ohkit-docs / main / Direct Upload; no settings were changed")
    return {
        "name": project["name"],
        "production_branch": project["production_branch"],
        "subdomain": project.get("subdomain"),
        "created": existing is None,
        "has_production_deployment": project.get("canonical_deployment") is not None,
    }


def main() -> None:
    try:
        summary = ensure_project()
    except (ValueError, RuntimeError, KeyError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(summary, sort_keys=True))
    print("Project verified. No deployment was uploaded and no DNS record was changed.")


if __name__ == "__main__":
    main()
