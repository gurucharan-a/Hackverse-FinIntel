from __future__ import annotations

import hashlib
import math
import re

POS = {
    "surge", "rally", "gain", "gains", "profit", "beat", "beats", "upgrade", "growth",
    "record", "strong", "bullish", "outperform", "expansion", "win", "positive",
    "higher", "rise", "rises", "rose", "upbeat", "buyback",
}
NEG = {
    "fall", "falls", "fell", "drop", "drops", "loss", "miss", "misses", "downgrade",
    "weak", "bearish", "probe", "fraud", "scam", "debt", "warning", "cut", "cuts",
    "decline", "slump", "crash", "negative", "layoff", "penalty", "fine",
}


def headline_sentiment(title: str) -> tuple[str, float]:
    tokens = re.findall(r"[a-z]+", (title or "").lower())
    p = sum(1 for t in tokens if t in POS)
    n = sum(1 for t in tokens if t in NEG)
    if p == 0 and n == 0:
        return "neutral", 0.4
    if p > n:
        return "positive", min(0.9, 0.5 + 0.1 * (p - n))
    if n > p:
        return "negative", min(0.9, 0.5 + 0.1 * (n - p))
    return "mixed", 0.5


def relevance_to_symbol(title: str, name: str | None, symbol: str) -> float:
    t = (title or "").lower()
    score = 0.35
    if symbol.lower().replace(".ns", "").replace(".bo", "") in t.replace(" ", ""):
        score += 0.4
    if name:
        first = name.split()[0].lower()
        if first in t:
            score += 0.25
    return round(min(score, 1.0), 2)


def clamp(n: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, n))


def uid(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None


    if isinstance(a, float) and math.isnan(a):
        return None
    return a / b
