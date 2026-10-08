"""Bind the fixed documentation domain and create its DNS record if absent."""

from __future__ import annotations

import json
from typing import Any

from create_docs_project import PROJECT, APIRequest, api_request, cloudflare_request

DOMAIN = "ohkit.wh1isper.top"
ZONE = "wh1isper.top"
TARGET = "ohkit-docs.pages.dev"


def ensure_domain(request: APIRequest = cloudflare_request) -> dict[str, Any]:
    path = f"/{PROJECT}/domains"
    domains = request("GET", path, None)["result"]
    if not isinstance(domains, list):
        raise ValueError("Cloudflare returned an invalid domain list")
    if not any(isinstance(domain, dict) and domain.get("name") == DOMAIN for domain in domains):
        print(f"Registering Pages domain {DOMAIN}", flush=True)
        request("POST", path, {"name": DOMAIN})
    domain = request("GET", f"{path}/{DOMAIN}", None)["result"]
    if not isinstance(domain, dict) or domain.get("name") != DOMAIN:
        raise ValueError("Cloudflare did not return the expected domain")
    return {"name": DOMAIN, "status": domain.get("status")}


def ensure_dns(request: APIRequest = api_request) -> None:
    print(f"Checking DNS for {DOMAIN}", flush=True)
    zones = request("GET", f"/zones?name={ZONE}&status=active", None)["result"]
    if not isinstance(zones, list) or len(zones) != 1 or zones[0].get("name") != ZONE:
        raise ValueError("The wh1isper.top zone is not uniquely visible; configure DNS in its provider")
    zone_id = zones[0]["id"]
    path = f"/zones/{zone_id}/dns_records"
    query = f"{path}?name={DOMAIN}"
    records = request("GET", query, None)["result"]
    if not isinstance(records, list):
        raise ValueError("Cloudflare returned invalid DNS records")
    if records:
        if len(records) != 1 or records[0].get("type") != "CNAME" or records[0].get("content") != TARGET:
            raise ValueError("Existing DNS conflicts with the Pages CNAME; no DNS record was changed")
    else:
        print(f"Creating CNAME {DOMAIN} -> {TARGET}", flush=True)
        request("POST", path, {"type": "CNAME", "name": DOMAIN, "content": TARGET, "ttl": 1, "proxied": True})
        records = request("GET", query, None)["result"]
        if not any(record.get("type") == "CNAME" and record.get("content") == TARGET for record in records):
            raise ValueError("DNS readback did not confirm the expected CNAME")
    print("DNS CNAME verified", flush=True)


def main() -> None:
    try:
        print(json.dumps(ensure_domain(), sort_keys=True), flush=True)
        ensure_dns()
        print(json.dumps(ensure_domain(), sort_keys=True), flush=True)
    except (ValueError, RuntimeError, KeyError) as error:
        raise SystemExit(str(error)) from None
    print("Domain configured. Verify activation and public HTTPS before declaring the site live.")


if __name__ == "__main__":
    main()
