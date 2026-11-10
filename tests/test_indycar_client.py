"""Offline tests for the INDYCAR HTTP client."""

from __future__ import annotations

import json
import urllib.error

import pytest

from utilities.indycar import client


class FakeResponse:
    """Minimal stand-in for urllib's HTTP response object."""

    def __init__(self, body=b"{}", status=200, headers=None):
        self._body = body
        self.status = status
        self.headers = headers or {}

    def read(self, size=-1):
        if size in (-1, None):
            return self._body
        return self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class RecordingUrlopen:
    """Capture requests while returning a fixed response or raising."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def install(monkeypatch, response=None, error=None):
    recorder = RecordingUrlopen(response=response, error=error)
    monkeypatch.setattr(client.urllib.request, "urlopen", recorder)
    return recorder


def json_response(payload, headers=None, status=200):
    return FakeResponse(
        body=json.dumps(payload).encode("utf-8"),
        status=status,
        headers=headers or {},
    )


# ---------------------------------------------------------------------------
# URL handling
# ---------------------------------------------------------------------------


def test_url_builds_every_known_feed():
    feeds = client.IndyCarFeeds()

    for name, path in client.FEED_PATHS.items():
        assert feeds.url(name) == f"{client.BASE_URL}/{path}"

    assert feeds.url("timing") == (
        "https://indycar.blob.core.windows.net/racecontrol/timingscoring-ris.json"
    )


def test_url_rejects_unknown_feed():
    feeds = client.IndyCarFeeds()

    with pytest.raises(ValueError, match="unknown INDYCAR feed"):
        feeds.url("results")


def test_url_strips_trailing_slash_from_custom_base():
    feeds = client.IndyCarFeeds(base_url="https://example.test/api/")

    assert feeds.url("schedule") == "https://example.test/api/schedulefeed.json"


# ---------------------------------------------------------------------------
# Successful fetches
# ---------------------------------------------------------------------------


def test_fetch_returns_json_and_metadata(monkeypatch):
    feeds = client.IndyCarFeeds(clock=lambda: 1234.5)
    recorder = install(
        monkeypatch,
        json_response(
            {"ok": True},
            headers={
                "ETag": '"v1"',
                "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
            },
        ),
    )

    result = feeds.timing()

    assert result.ok is True
    assert result.name == "timing"
    assert result.data == {"ok": True}
    assert result.status == 200
    assert result.etag == '"v1"'
    assert result.last_modified == "Mon, 01 Jan 2024 00:00:00 GMT"
    assert result.fetched_at == 1234.5
    assert result.not_modified is False
    assert result.error == ""

    request, timeout = recorder.requests[0]
    assert request.full_url == (
        f"{client.BASE_URL}/{client.FEED_PATHS['timing']}?cb=1234500"
    )
    assert timeout == client.HTTP_TIMEOUT
    assert request.get_header("User-agent") == client.USER_AGENT
    assert request.get_header("Accept") == "application/json"


def test_fetch_uses_conditional_headers_without_cache_buster(monkeypatch):
    feeds = client.IndyCarFeeds()
    recorder = install(monkeypatch, json_response({}))

    feeds.schedule(
        etag='"v1"',
        last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
    )

    request, _ = recorder.requests[0]
    assert "?cb=" not in request.full_url
    assert request.get_header("If-none-match") == '"v1"'
    assert request.get_header("If-modified-since") == ("Mon, 01 Jan 2024 00:00:00 GMT")


def test_fetch_can_skip_cache_buster_without_conditional_headers(monkeypatch):
    feeds = client.IndyCarFeeds()
    recorder = install(monkeypatch, json_response({}))

    feeds.activity(cache_bust=False)

    request, _ = recorder.requests[0]
    assert "?cb=" not in request.full_url
    assert request.get_header("If-none-match") is None


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


def test_fetch_handles_not_modified(monkeypatch):
    url = f"{client.BASE_URL}/{client.FEED_PATHS['schedule']}"
    error = urllib.error.HTTPError(
        url,
        304,
        "Not Modified",
        {"ETag": '"v2"'},
        None,
    )
    feeds = client.IndyCarFeeds(clock=lambda: 50.0)
    install(monkeypatch, error=error)

    result = feeds.schedule(
        etag='"v1"',
        last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
    )

    assert result.not_modified is True
    assert result.status == 304
    assert result.etag == '"v2"'
    assert result.last_modified == "Mon, 01 Jan 2024 00:00:00 GMT"
    assert result.fetched_at == 50.0
    assert result.ok is False
    assert result.error == ""


def test_fetch_reports_http_errors(monkeypatch):
    error = urllib.error.HTTPError(
        "https://example.test", 503, "Service Unavailable", {}, None
    )
    feeds = client.IndyCarFeeds()
    install(monkeypatch, error=error)

    result = feeds.drivers()

    assert result.status == 503
    assert result.error == "HTTP 503: Service Unavailable"
    assert result.data is None
    assert result.ok is False


def test_fetch_reports_network_errors(monkeypatch):
    feeds = client.IndyCarFeeds()
    install(monkeypatch, error=TimeoutError("timed out"))

    result = feeds.tsconfig()

    assert result.status == 0
    assert result.error == "TimeoutError: timed out"
    assert result.ok is False


def test_fetch_rejects_invalid_json(monkeypatch):
    feeds = client.IndyCarFeeds()
    install(monkeypatch, FakeResponse(body=b"<html>not json</html>"))

    result = feeds.timing()

    assert result.status == 200
    assert result.data is None
    assert result.error.startswith("invalid JSON:")
    assert result.ok is False


def test_fetch_rejects_oversized_response(monkeypatch):
    feeds = client.IndyCarFeeds()
    install(monkeypatch, FakeResponse(body=b"x" * (client.MAX_BYTES + 1)))

    result = feeds.timing()

    assert result.error == f"response exceeds {client.MAX_BYTES} bytes"
    assert result.ok is False


def test_fetch_uses_per_call_timeout(monkeypatch):
    feeds = client.IndyCarFeeds(timeout=10.0)
    recorder = install(monkeypatch, json_response({}))

    feeds.timing(timeout=3.0)

    _, timeout = recorder.requests[0]
    assert timeout == 3.0


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------


def test_named_helpers_call_fetch_with_their_feed(monkeypatch):
    feeds = client.IndyCarFeeds()
    calls = []

    def fake_fetch(name, **kwargs):
        calls.append((name, kwargs))
        return client.FeedResult(name=name, data={})

    monkeypatch.setattr(feeds, "fetch", fake_fetch)

    assert feeds.timing(timeout=3).data == {}
    assert feeds.tsconfig(timeout=3).data == {}
    assert feeds.activity(timeout=3).data == {}
    assert feeds.schedule(timeout=3).data == {}
    assert feeds.drivers(timeout=3).data == {}

    assert [name for name, _ in calls] == [
        "timing",
        "tsconfig",
        "activity",
        "schedule",
        "drivers",
    ]
    assert all(kwargs == {"timeout": 3} for _, kwargs in calls)
