"""The read API fails closed.

The app is otherwise stateless by design — "no visitor can see another's
conversation" is true because nothing is stored. Persisting traces ends that,
so this route is the one place the property now has to be defended.
"""
import pytest
from fastapi.testclient import TestClient

from server import trace_store
from server.app import create_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACE_DB", str(tmp_path / "traces.db"))


def stored(question="How congested is SFO?"):
    record = trace_store.make_record(
        question=question, answer="About 81% full.", model="claude-opus-5",
        steps=[{"kind": "tool", "round": 1, "ms": 1810, "name": "get_congestion",
                "args": {"airport": "SFO"}, "result": {"load_factor": 80.9},
                "error": None}],
        latency_ms=3050)
    trace_store.write(record)
    return record


def keyed(monkeypatch, fake, key="s3cret"):
    monkeypatch.setenv("TRACE_KEY", key)
    return TestClient(create_app(conversation_factory=fake))


def test_the_routes_do_not_exist_without_a_key(monkeypatch, fake):
    monkeypatch.delenv("TRACE_KEY", raising=False)
    client = TestClient(create_app(conversation_factory=fake))
    stored()

    assert client.get("/api/traces").status_code == 404


def test_a_wrong_key_is_404_not_403(monkeypatch, fake):
    """404 so a prober cannot tell 'wrong key' from 'no such route'."""
    client = keyed(monkeypatch, fake)
    stored()

    assert client.get("/api/traces",
                      headers={"X-Trace-Key": "wrong"}).status_code == 404


def test_a_missing_header_is_404(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    stored()

    assert client.get("/api/traces").status_code == 404


def test_the_right_key_lists_summaries_newest_first(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    stored("first")
    stored("second")

    body = client.get("/api/traces", headers={"X-Trace-Key": "s3cret"}).json()
    assert [row["question"] for row in body["traces"]] == ["second", "first"]
    assert "steps" not in body["traces"][0]
    assert body["traces"][0]["step_count"] == 1


def test_limit_and_offset_pass_through(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    for question in ["a", "b", "c"]:
        stored(question)

    body = client.get("/api/traces?limit=1&offset=1",
                      headers={"X-Trace-Key": "s3cret"}).json()
    assert [row["question"] for row in body["traces"]] == ["b"]


def test_one_trace_comes_back_whole(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    record = stored()

    body = client.get(f"/api/traces/{record['id']}",
                      headers={"X-Trace-Key": "s3cret"}).json()
    assert body["steps"][0]["name"] == "get_congestion"
    assert body["steps"][0]["result"] == {"load_factor": 80.9}


def test_an_unknown_trace_id_is_404(monkeypatch, fake):
    client = keyed(monkeypatch, fake)

    assert client.get("/api/traces/no-such-id",
                      headers={"X-Trace-Key": "s3cret"}).status_code == 404


def test_a_wrong_key_404_is_byte_identical_to_a_missing_route_404(monkeypatch, fake):
    """Status code alone isn't enough — a distinct body would let a prober
    tell 'wrong key' apart from 'no tracing API at all' even though both
    return 404."""
    monkeypatch.delenv("TRACE_KEY", raising=False)
    no_route_body = TestClient(
        create_app(conversation_factory=fake)).get("/api/traces").json()

    client = keyed(monkeypatch, fake)
    wrong_key_body = client.get(
        "/api/traces", headers={"X-Trace-Key": "wrong"}).json()

    assert wrong_key_body == no_route_body


def test_a_negative_limit_does_not_bypass_the_cap(monkeypatch, fake):
    """SQLite treats a negative LIMIT as 'no limit' — the route must clamp
    it, not pass it straight through."""
    client = keyed(monkeypatch, fake)
    for question in ["a", "b", "c"]:
        stored(question)

    body = client.get("/api/traces?limit=-1",
                      headers={"X-Trace-Key": "s3cret"}).json()
    assert len(body["traces"]) == 1


def test_a_malformed_limit_is_404_not_422_without_a_key(monkeypatch, fake):
    """A non-integer `limit` must not let FastAPI's automatic validation
    answer BEFORE authorised() runs — that would let a prober tell 'TRACE_KEY
    is configured here' (422) apart from 'no tracing API at all' (404)
    without ever needing the key."""
    client = keyed(monkeypatch, fake)
    stored()

    response = client.get("/api/traces?limit=abc",
                          headers={"X-Trace-Key": "wrong"})
    assert response.status_code == 404


def test_a_malformed_limit_with_no_header_is_still_404(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    stored()

    response = client.get("/api/traces?limit=abc")
    assert response.status_code == 404


def test_a_malformed_limit_404_is_byte_identical_to_a_missing_route_404(
        monkeypatch, fake):
    """Belt and suspenders on the byte-identity guarantee: a malformed
    `limit` must not change the 404 body either."""
    monkeypatch.delenv("TRACE_KEY", raising=False)
    no_route_body = TestClient(
        create_app(conversation_factory=fake)).get(
            "/api/traces?limit=abc").json()

    client = keyed(monkeypatch, fake)
    wrong_key_body = client.get(
        "/api/traces?limit=abc", headers={"X-Trace-Key": "wrong"}).json()

    assert wrong_key_body == no_route_body


def test_a_non_ascii_trace_key_header_is_404_not_500(monkeypatch, fake):
    """hmac.compare_digest() raises TypeError on non-ASCII strings; Starlette
    decodes headers as latin-1, so a raw client CAN send a non-ASCII byte here
    even though some Python HTTP clients refuse to. authorised() must catch
    that and fail closed, not let it surface as an uncaught 500 — which would
    be yet another way to distinguish 'TRACE_KEY is set' from 'no route'.

    httpx's own str-header path rejects non-ASCII with a UnicodeEncodeError
    before the request is even built, so the non-ASCII byte is sent as raw
    latin-1-encoded bytes instead — this is what a raw HTTP client (curl, a
    hand-built ASGI request) can do even though httpx's convenience str path
    can't.
    """
    client = keyed(monkeypatch, fake)
    stored()

    response = client.get(
        "/api/traces", headers={"X-Trace-Key": "café".encode("latin-1")})
    assert response.status_code == 404


def test_a_non_ascii_trace_key_on_the_single_trace_route_is_404_not_500(
        monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    record = stored()

    response = client.get(
        f"/api/traces/{record['id']}",
        headers={"X-Trace-Key": "naïve".encode("latin-1")})
    assert response.status_code == 404


def test_authorised_fails_closed_against_a_non_ascii_configured_key(monkeypatch):
    """If TRACE_KEY itself contains a non-ASCII character (e.g. copy-pasted
    from a password generator), hmac.compare_digest(trace_key, given) raises
    on trace_key alone — even for a correctly-keyed request. authorised()
    must fail closed here too rather than 500 forever. Exercised directly
    against the function since httpx cannot easily send a request that would
    also need a non-ASCII env var to match."""
    import server.app as app_module

    monkeypatch.setenv("TRACE_KEY", "café")
    app = app_module.create_app()
    # Recover the same closure FastAPI wired up, via a request TestClient
    # can actually send: any header value the client is willing to send will
    # fail the comparison against the non-ASCII trace_key without raising.
    client = TestClient(app)
    response = client.get("/api/traces", headers={"X-Trace-Key": "s3cret"})
    assert response.status_code == 404
