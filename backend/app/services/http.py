from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import HTTP_TIMEOUT, USER_AGENT
from app.db import log_api


def http_client() -> httpx.Client:
    return httpx.Client(
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"},
        follow_redirects=True,
    )


def timed_get(provider: str, url: str, **kwargs: Any) -> tuple[httpx.Response | None, float, str | None]:
    t0 = time.perf_counter()
    error = None
    resp = None
    try:
        with http_client() as c:
            resp = c.get(url, **kwargs)
            resp.raise_for_status()
    except Exception as exc:
        error = str(exc)[:400]
        resp = None
    latency = (time.perf_counter() - t0) * 1000
    log_api(provider, url[:180], resp is not None, latency, error)
    return resp, latency, error


def timed_call(provider: str, endpoint: str, fn):
    t0 = time.perf_counter()
    error = None
    result = None
    try:
        result = fn()
    except Exception as exc:
        error = str(exc)[:400]
    latency = (time.perf_counter() - t0) * 1000
    ok = error is None and result is not None
    log_api(provider, endpoint, ok, latency, error)
    return result, latency, error
