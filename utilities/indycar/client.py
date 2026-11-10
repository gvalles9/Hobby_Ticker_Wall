"""HTTP client for the public INDYCAR leaderboard feeds.

The endpoints are the official site's own Azure Blob JSON feeds.  They are
not a documented public API, so this module treats every response as
best-effort data and never raises into the caller's render loop.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

BASE_URL = "https://indycar.blob.core.windows.net/racecontrol"

FEED_PATHS = {
    "timing": "timingscoring-ris.json",
    "tsconfig": "tsconfig.json",
    "activity": "trackactivityleaderboardfeed.json",
    "schedule": "schedulefeed.json",
    "drivers": "driversfeed.json",
}

USER_AGENT = (
    "HobbyTicker/1.0 (INDYCAR feed client; "
    "+https://github.com/gvalles9/Hobby_Ticker_Wall)"
)
HTTP_TIMEOUT = 10.0
MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class FeedResult:
    """One feed request, successful or not."""

    name: str
    data: Any = None
    status: int = 0
    etag: str = ""
    last_modified: str = ""
    fetched_at: float = 0.0
    not_modified: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        """True when the request produced usable JSON."""
        return self.error == "" and self.data is not None


def _header(headers: Any, name: str) -> str:
    """Read a header from urllib's HTTPMessage or a plain mapping."""
    if headers is None:
        return ""
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return ""
    return str(getter(name) or "")


class IndyCarFeeds:
    """Fetch raw JSON payloads from the INDYCAR race-control feeds."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = HTTP_TIMEOUT,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.clock = clock

    def url(self, name: str) -> str:
        """Return the endpoint for a logical feed name."""
        try:
            path = FEED_PATHS[name]
        except KeyError as exc:
            raise ValueError(f"unknown INDYCAR feed: {name!r}") from exc
        return f"{self.base_url}/{path}"

    def fetch(
        self,
        name: str,
        *,
        etag: str = "",
        last_modified: str = "",
        cache_bust: bool = True,
        timeout: float | None = None,
    ) -> FeedResult:
        """Fetch one feed.

        Conditional headers are used when an ETag or Last-Modified value is
        supplied; in that case the cache-busting query string is omitted so
        the server can answer with 304 Not Modified.
        """
        url = self.url(name)
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        conditional = bool(etag or last_modified)
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        if cache_bust and not conditional:
            url = f"{url}?cb={int(self.clock() * 1000)}"

        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(
                request, timeout=timeout or self.timeout
            ) as response:
                body = response.read(MAX_BYTES + 1)
                status = int(getattr(response, "status", 200) or 200)
                response_headers = getattr(response, "headers", None)
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return FeedResult(
                    name=name,
                    status=304,
                    etag=_header(exc.headers, "ETag") or etag,
                    last_modified=(
                        _header(exc.headers, "Last-Modified") or last_modified
                    ),
                    fetched_at=self.clock(),
                    not_modified=True,
                )
            return FeedResult(
                name=name,
                status=exc.code,
                error=f"HTTP {exc.code}: {exc.reason}",
                fetched_at=self.clock(),
            )
        except Exception as exc:  # network, timeout, TLS, DNS, ...
            return FeedResult(
                name=name,
                error=f"{type(exc).__name__}: {exc}",
                fetched_at=self.clock(),
            )

        if len(body) > MAX_BYTES:
            return FeedResult(
                name=name,
                status=status,
                error=f"response exceeds {MAX_BYTES} bytes",
                fetched_at=self.clock(),
            )

        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return FeedResult(
                name=name,
                status=status,
                error=f"invalid JSON: {exc}",
                fetched_at=self.clock(),
            )

        return FeedResult(
            name=name,
            data=data,
            status=status,
            etag=_header(response_headers, "ETag"),
            last_modified=_header(response_headers, "Last-Modified"),
            fetched_at=self.clock(),
        )

    def timing(self, **kwargs: Any) -> FeedResult:
        """Live timing and scoring feed."""
        return self.fetch("timing", **kwargs)

    def tsconfig(self, **kwargs: Any) -> FeedResult:
        """Track-activity flags and display overrides."""
        return self.fetch("tsconfig", **kwargs)

    def activity(self, **kwargs: Any) -> FeedResult:
        """Event and session activity feed."""
        return self.fetch("activity", **kwargs)

    def schedule(self, **kwargs: Any) -> FeedResult:
        """Season schedule feed."""
        return self.fetch("schedule", **kwargs)

    def drivers(self, **kwargs: Any) -> FeedResult:
        """Driver directory and season stats feed."""
        return self.fetch("drivers", **kwargs)
