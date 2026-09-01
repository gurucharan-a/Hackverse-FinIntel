from __future__ import annotations

from typing import Any

from app.db import db
from app.services.data_providers.market_provider import market_provider


def portfolio_snapshot(user_id: str = "local") -> dict[str, Any]:
    with db() as conn:
        profile = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        holdings = [dict(r) for r in conn.execute("SELECT * FROM portfolio_holdings WHERE user_id = ?", (user_id,)).fetchall()]
    rows = []
    total = 0.0
    cost = 0.0
    day_pnl = 0.0
    sectors: dict[str, float] = {}
    unavailable = 0
    for h in holdings:
        q = market_provider.quote(h["yahoo_symbol"])
        px = q.price if q.available else None
        qty = float(h["quantity"])
        avg = float(h["avg_price"])
        value = px * qty if px is not None else None
        pnl = (px - avg) * qty if px is not None else None
        chg = q.change * qty if q.available and q.change is not None else None
        if value is not None:
            total += value
            sectors[h.get("sector") or q.sector or "Unknown"] = sectors.get(h.get("sector") or q.sector or "Unknown", 0) + value
        else:
            unavailable += 1
        cost += avg * qty
        if chg is not None:
            day_pnl += chg
        rows.append(
            {
                **h,
                "price": px,
                "value": value,
                "pnl": pnl,
                "pnl_pct": ((px / avg - 1) * 100) if px and avg else None,
                "change_pct": q.change_pct if q.available else None,
                "quote_meta": q.meta.model_dump(),
                "available": q.available,
            }
        )
    for r in rows:
        r["allocation"] = round(r["value"] / total * 100, 2) if total and r["value"] is not None else None
    overall_pnl = total - cost if total else None
    hhi = sum(((r["value"] / total) ** 2) for r in rows if r["value"] and total) if total else None
    n = len([r for r in rows if r["available"]])
    diversification = None
    if hhi is not None and n:
        diversification = round(max(0, min(100, (1 - hhi) / (1 - 1 / max(n, 1)) * 100 if n > 1 else 0)), 1)
    risk_score = None
    if hhi is not None:
        risk_score = round(min(100, hhi * 100 + (20 if unavailable else 0)), 1)
    return {
        "holdings": rows,
        "total_value": round(total, 2) if total else None,
        "today_pnl": round(day_pnl, 2) if rows else None,
        "overall_pnl": round(overall_pnl, 2) if overall_pnl is not None else None,
        "overall_pnl_pct": round((overall_pnl / cost) * 100, 2) if overall_pnl is not None and cost else None,
        "risk_score": risk_score,
        "diversification_score": diversification,
        "sectors": {k: round(v, 2) for k, v in sectors.items()},
        "unavailable_marks": unavailable,
        "profile": dict(profile) if profile else None,
        "note": "DATA UNAVAILABLE" if not total else None,
    }
