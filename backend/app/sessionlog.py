from __future__ import annotations

import json
from pathlib import Path

from app.models import SessionMetrics

LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "sessions.jsonl"


def persist(metrics: SessionMetrics) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(metrics.model_dump_json() + "\n")


def recent(limit: int = 20) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))
