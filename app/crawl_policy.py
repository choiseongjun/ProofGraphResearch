"""Polite, deterministic crawling rules shared by interactive and batch ingestion."""
from __future__ import annotations

import time
from threading import Lock
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_last_request_by_host: dict[str, float] = {}
_lock = Lock()
_tracking_parameters = {"gclid", "fbclid", "mc_cid", "mc_eid"}


def canonical_url(value: str) -> str:
    parsed = urlparse(value)
    query = [(key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in _tracking_parameters]
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", urlencode(sorted(query)), ""))


def wait_for_host(url: str, interval_seconds: float) -> None:
    host = urlparse(url).netloc.lower()
    with _lock:
        elapsed = time.monotonic() - _last_request_by_host.get(host, 0.0)
        delay = max(0.0, interval_seconds - elapsed)
        if delay:
            time.sleep(delay)
        _last_request_by_host[host] = time.monotonic()
