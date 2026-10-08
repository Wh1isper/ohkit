import pytest
from configure_docs_domain import DOMAIN, TARGET, ensure_dns, ensure_domain


@pytest.mark.parametrize("exists", [True, False])
def test_domain_registration_reads_before_writing_and_verifies(exists):
    calls = []
    domain = {"name": DOMAIN, "status": "pending"}

    def request(method, path, payload):
        calls.append((method, path, payload))
        if path.endswith("/domains") and method == "GET":
            return {"result": [domain] if exists else []}
        return {"result": domain}

    assert ensure_domain(request) == domain
    assert [call[0] for call in calls] == (["GET", "GET"] if exists else ["GET", "POST", "GET"])
    if not exists:
        assert calls[1] == ("POST", "/ohkit-docs/domains", {"name": DOMAIN})


def test_domain_lookup_failure_never_creates():
    def request(method, path, payload):
        assert method == "GET"
        raise RuntimeError("permission denied")

    with pytest.raises(RuntimeError, match="permission denied"):
        ensure_domain(request)


@pytest.mark.parametrize("exists", [True, False])
def test_dns_creates_only_missing_record_and_reads_back(exists):
    calls = []
    record = {"name": DOMAIN, "type": "CNAME", "content": TARGET}

    def request(method, path, payload):
        calls.append((method, path, payload))
        if path.startswith("/zones?"):
            return {"result": [{"name": "wh1isper.top", "id": "zone-id"}]}
        if method == "POST":
            assert payload == record | {"ttl": 1, "proxied": True}
            return {"result": record}
        return {"result": [record] if exists or len(calls) > 2 else []}

    ensure_dns(request)
    assert [call[0] for call in calls] == (["GET", "GET"] if exists else ["GET", "GET", "POST", "GET"])


@pytest.mark.parametrize(
    "records",
    [[{"type": "A", "content": "192.0.2.1"}], [{"type": "CNAME", "content": "other.example"}]],
)
def test_conflicting_dns_is_never_overwritten(records):
    def request(method, path, payload):
        assert method == "GET"
        if path.startswith("/zones?"):
            return {"result": [{"name": "wh1isper.top", "id": "zone-id"}]}
        return {"result": records}

    with pytest.raises(ValueError, match="conflicts"):
        ensure_dns(request)


def test_invisible_zone_never_writes():
    def request(method, path, payload):
        assert method == "GET"
        return {"result": []}

    with pytest.raises(ValueError, match="not uniquely visible"):
        ensure_dns(request)
