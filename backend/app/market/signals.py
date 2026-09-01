from __future__ import annotations

from app.models import Citation, DimensionSignal, MarketTick, SignalLabel


def _label(score: float, *, degraded: bool = False) -> SignalLabel:
    if degraded:
        return "unavailable"
    if score >= 0.55:
        return "strong_buy_pressure"
    if score >= 0.18:
        return "buy_pressure"
    if score <= -0.55:
        return "strong_sell_pressure"
    if score <= -0.18:
        return "sell_pressure"
    return "neutral"


def classify(tick: MarketTick) -> list[DimensionSignal]:
    """Three independent dimensions: momentum, volume anomaly, sentiment."""
    degraded = tick.feed_status == "degraded"

    mom_score = max(-1.0, min(1.0, tick.momentum_20d / 0.12 + (tick.rsi_14 - 50) / 80))
    vol_ratio = 0.0 if tick.avg_volume_20d == 0 else tick.volume / tick.avg_volume_20d
    vol_score = max(-1.0, min(1.0, (vol_ratio - 1.0) * (1 if tick.change_pct >= 0 else -1)))
    sent_score = max(
        -1.0,
        min(
            1.0,
            tick.fii_net_cr / 1000.0 + (1.0 - tick.put_call_ratio) * 0.6,
        ),
    )

    if degraded:
        mom_score = vol_score = sent_score = 0.0

    mom_conf = 0.15 if degraded else min(0.92, 0.55 + abs(mom_score) * 0.4)
    vol_conf = 0.12 if degraded else min(0.9, 0.5 + min(abs(vol_ratio - 1.0), 1.5) * 0.25)
    sent_conf = 0.12 if degraded else min(0.88, 0.5 + abs(sent_score) * 0.35)

    feed_cite = Citation(
        source_id=f"feed:{tick.symbol}",
        title=f"{tick.symbol} tape ({tick.feed_status})",
        excerpt=(
            f"Last {tick.last:.2f} ({tick.change_pct:+.2f}%), RSI {tick.rsi_14:.1f}, "
            f"20d momentum {tick.momentum_20d*100:.1f}%, vol {tick.volume:,} vs 20d avg {tick.avg_volume_20d:,}, "
            f"FII net ₹{tick.fii_net_cr:.0f} Cr, PCR {tick.put_call_ratio:.2f}."
        ),
        as_of=tick.as_of.isoformat(),
        score=1.0,
    )

    gap = "Price feed degraded — dimension marked unavailable rather than invented."
    return [
        DimensionSignal(
            dimension="price_momentum",
            label=_label(mom_score, degraded=degraded),
            score=round(mom_score, 3),
            confidence=round(mom_conf, 3),
            reasoning=gap
            if degraded
            else (
                f"20-day momentum is {tick.momentum_20d*100:.1f}% with RSI-14 at {tick.rsi_14:.1f}. "
                + (
                    "Trend is extended; chase risk is elevated."
                    if tick.rsi_14 >= 70
                    else "Trend is constructive but not overbought."
                    if mom_score > 0
                    else "Trend is soft; no momentum confirmation."
                )
            ),
            citations=[feed_cite],
            degraded=degraded,
        ),
        DimensionSignal(
            dimension="volume_anomaly",
            label=_label(vol_score, degraded=degraded),
            score=round(vol_score, 3),
            confidence=round(vol_conf, 3),
            reasoning=gap
            if degraded
            else (
                f"Session volume is {vol_ratio:.2f}× the 20-day average. "
                + (
                    "This is a statistically large participation spike in the direction of the print."
                    if vol_ratio >= 1.6
                    else "Participation is near normal; the move lacks volume confirmation."
                )
            ),
            citations=[feed_cite],
            degraded=degraded,
        ),
        DimensionSignal(
            dimension="sentiment",
            label=_label(sent_score, degraded=degraded),
            score=round(sent_score, 3),
            confidence=round(sent_conf, 3),
            reasoning=gap
            if degraded
            else (
                f"FII net flow ₹{tick.fii_net_cr:.0f} Cr and options PCR {tick.put_call_ratio:.2f}. "
                + (
                    "Low PCR implies crowded call positioning — squeeze risk both ways."
                    if tick.put_call_ratio < 0.7
                    else "Flows and options skew are not extreme."
                )
            ),
            citations=[feed_cite],
            degraded=degraded,
        ),
    ]
