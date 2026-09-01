from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype="float64")


def sma(values: list[float], window: int) -> list[float | None]:
    if len(values) < window:
        return [None] * len(values)
    s = _series(values).rolling(window=window, min_periods=window).mean()
    return [None if math.isnan(x) else float(x) for x in s.tolist()]


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    s = _series(values)
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, math.nan)
    val = 100 - (100 / (1 + rs.iloc[-1]))
    if val is None or math.isnan(val):
        return None
    return round(float(val), 2)


def macd(values: list[float]) -> dict[str, float | None]:
    if len(values) < 26:
        return {"macd": None, "signal": None, "hist": None}
    s = _series(values)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    sig = line.ewm(span=9, adjust=False).mean()
    hist = line - sig
    def last(x):
        v = float(x.iloc[-1])
        return None if math.isnan(v) else round(v, 4)
    return {"macd": last(line), "signal": last(sig), "hist": last(hist)}


def realized_vol(values: list[float], window: int = 20) -> float | None:
    if len(values) < window + 1:
        return None
    rets = _series(values).pct_change().dropna()
    if len(rets) < window:
        return None
    v = float(rets.tail(window).std() * math.sqrt(252) * 100)
    return round(v, 2)


def momentum(values: list[float], window: int = 20) -> float | None:
    if len(values) < window + 1:
        return None
    a, b = values[-1], values[-1 - window]
    if not b:
        return None
    return round((a / b - 1) * 100, 2)


def last_value(series: list[float | None]) -> float | None:
    for x in reversed(series):
        if x is not None:
            return x
    return None


def support_resistance(values: list[float], lookback: int = 60) -> dict[str, float | None]:
    window = values[-lookback:] if len(values) >= 5 else values
    if not window:
        return {"support": None, "resistance": None}
    return {"support": round(min(window), 2), "resistance": round(max(window), 2)}


def volume_ratio(volumes: list[float], window: int = 20) -> float | None:
    if len(volumes) < window:
        return None
    avg = sum(volumes[-window:-1]) / max(window - 1, 1)
    if avg <= 0:
        return None
    return round(volumes[-1] / avg, 2)


def compute_stack(closes: list[float], volumes: list[float]) -> dict[str, Any]:
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    return {
        "rsi": rsi(closes),
        "macd": macd(closes),
        "sma20": last_value(sma20),
        "sma50": last_value(sma50),
        "sma20_series": sma20,
        "sma50_series": sma(closes, 50),
        "volatility": realized_vol(closes),
        "momentum_20": momentum(closes, 20),
        "volume_ratio": volume_ratio(volumes),
        **support_resistance(closes),
    }
