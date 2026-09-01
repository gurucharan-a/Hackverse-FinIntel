from __future__ import annotations

from datetime import datetime, timezone

from app.models import MarketTick

# Seeded NSE-like tape. Values are internally consistent for the demo window
# (session date 2026-09-01). Forward 30d returns power the accuracy proxy.
UNIVERSE: dict[str, dict] = {
    "RELIANCE": {
        "name": "Reliance Industries",
        "sector": "Energy / Conglomerate",
        "last": 2984.50,
        "change_pct": 1.82,
        "volume": 9_420_000,
        "avg_volume_20d": 5_110_000,
        "rsi_14": 64.2,
        "momentum_20d": 0.068,
        "vwap_dev_pct": 0.9,
        "fii_net_cr": 842.0,
        "put_call_ratio": 0.78,
        "fwd_30d_return": 0.041,
    },
    "INFY": {
        "name": "Infosys",
        "sector": "IT Services",
        "last": 1872.10,
        "change_pct": -0.64,
        "volume": 4_180_000,
        "avg_volume_20d": 4_050_000,
        "rsi_14": 48.1,
        "momentum_20d": -0.012,
        "vwap_dev_pct": -0.3,
        "fii_net_cr": -126.0,
        "put_call_ratio": 1.05,
        "fwd_30d_return": 0.018,
    },
    "HDFCBANK": {
        "name": "HDFC Bank",
        "sector": "Private Banks",
        "last": 1648.75,
        "change_pct": 0.41,
        "volume": 12_300_000,
        "avg_volume_20d": 11_800_000,
        "rsi_14": 55.4,
        "momentum_20d": 0.021,
        "vwap_dev_pct": 0.2,
        "fii_net_cr": 310.0,
        "put_call_ratio": 0.94,
        "fwd_30d_return": 0.027,
    },
    "ZOMATO": {
        "name": "Eternal Ltd (Zomato)",
        "sector": "Consumer Internet",
        "last": 268.40,
        "change_pct": 4.12,
        "volume": 86_500_000,
        "avg_volume_20d": 28_200_000,
        "rsi_14": 78.6,
        "momentum_20d": 0.214,
        "vwap_dev_pct": 3.8,
        "fii_net_cr": 95.0,
        "put_call_ratio": 0.52,
        "fwd_30d_return": -0.093,
    },
    "PAYTM": {
        "name": "One97 Communications",
        "sector": "Fintech",
        "last": 612.30,
        "change_pct": -2.18,
        "volume": 7_640_000,
        "avg_volume_20d": 6_900_000,
        "rsi_14": 41.0,
        "momentum_20d": -0.087,
        "vwap_dev_pct": -1.4,
        "fii_net_cr": -48.0,
        "put_call_ratio": 1.22,
        "fwd_30d_return": -0.054,
    },
}

_jitter_step = 0


def snapshot(symbol: str, *, feed_down: bool = False, t: datetime | None = None) -> MarketTick:
    global _jitter_step
    raw = UNIVERSE[symbol]
    _jitter_step += 1
    # Tiny live-feel wobble that does not change classification.
    wobble = ((_jitter_step % 7) - 3) * 0.00015
    last = round(raw["last"] * (1 + wobble), 2)
    status: str = "degraded" if feed_down else "simulated"
    if feed_down:
        return MarketTick(
            symbol=symbol,
            name=raw["name"],
            last=last,
            change_pct=0.0,
            volume=0,
            avg_volume_20d=raw["avg_volume_20d"],
            rsi_14=50.0,
            momentum_20d=0.0,
            vwap_dev_pct=0.0,
            fii_net_cr=0.0,
            put_call_ratio=1.0,
            sector=raw["sector"],
            as_of=t or datetime.now(timezone.utc),
            feed_status="degraded",
        )
    return MarketTick(
        symbol=symbol,
        name=raw["name"],
        last=last,
        change_pct=raw["change_pct"] + wobble * 100,
        volume=raw["volume"],
        avg_volume_20d=raw["avg_volume_20d"],
        rsi_14=raw["rsi_14"],
        momentum_20d=raw["momentum_20d"],
        vwap_dev_pct=raw["vwap_dev_pct"],
        fii_net_cr=raw["fii_net_cr"],
        put_call_ratio=raw["put_call_ratio"],
        sector=raw["sector"],
        as_of=t or datetime.now(timezone.utc),
        feed_status=status,  # type: ignore[arg-type]
    )


def all_ticks(feed_down_symbol: str | None = None) -> list[MarketTick]:
    return [snapshot(s, feed_down=(s == feed_down_symbol)) for s in UNIVERSE]


def forward_return(symbol: str) -> float:
    return float(UNIVERSE[symbol]["fwd_30d_return"])
