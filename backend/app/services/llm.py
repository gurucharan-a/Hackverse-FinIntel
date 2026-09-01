from __future__ import annotations

import os
from typing import Any

from app.config import LLM_KEY_SET, OPENAI_BASE_URL, OPENAI_MODEL
from app.services.http import http_client
from app.db import log_api
import time


def llm_available() -> bool:
    return LLM_KEY_SET


def complete(system: str, user: str, max_tokens: int = 500) -> str | None:
    if not LLM_KEY_SET:
        return None
    key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    url = OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": system
                + " Use only facts present in the user message. If a fact is missing, say INSUFFICIENT EVIDENCE. Never invent prices, filings, or citations.",
            },
            {"role": "user", "content": user},
        ],
    }
    t0 = time.perf_counter()
    try:
        with http_client() as c:
            r = c.post(url, json=payload, headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        log_api("llm", url, True, (time.perf_counter() - t0) * 1000, None)
        return text
    except Exception as exc:
        log_api("llm", url, False, (time.perf_counter() - t0) * 1000, str(exc)[:300])
        return None
