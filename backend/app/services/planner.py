from __future__ import annotations

import json
from typing import Any

from app.db import db
from app.services.data_providers.market_provider import market_provider
from app.services.indicators import realized_vol
from app.services.llm import complete, llm_available


UNIVERSE = [
    ("RELIANCE.NS", "Reliance Industries", "Energy"),
    ("TCS.NS", "Tata Consultancy Services", "Information Technology"),
    ("HDFCBANK.NS", "HDFC Bank", "Financials"),
    ("INFY.NS", "Infosys", "Information Technology"),
    ("HINDUNILVR.NS", "Hindustan Unilever", "Consumer"),
    ("ITC.NS", "ITC", "Consumer"),
    ("SBIN.NS", "State Bank of India", "Financials"),
]


def generate_plan(capital: float, monthly: float, risk: str, horizon: str, objective: str) -> dict[str, Any]:
    ranked = []
    for ysym, name, sector in UNIVERSE:
        hist = market_provider.history(ysym, "1Y")
        closes = [b.close for b in hist.bars]
        vol = realized_vol(closes) if hist.available else None
        q = market_provider.quote(ysym)
        ranked.append(
            {
                "symbol": ysym.replace(".NS", ""),
                "yahoo_symbol": ysym,
                "name": name,
                "sector": sector,
                "volatility": vol,
                "price": q.price if q.available else None,
                "available": q.available and vol is not None,
            }
        )
    usable = [r for r in ranked if r["available"]]
    if not usable:
        return {
            "available": False,
            "error": "INSUFFICIENT EVIDENCE — could not retrieve enough historical volatility to build a plan.",
            "language": "research",
        }
    usable.sort(key=lambda x: x["volatility"])
    if risk == "conservative":
        picks = usable[:3]
        equity_pct = 40
        cash_pct = 60
    elif risk == "aggressive":
        picks = usable[-3:]
        equity_pct = 85
        cash_pct = 15
    else:
        picks = usable[1:4] if len(usable) >= 4 else usable
        equity_pct = 65
        cash_pct = 35
    n = max(len(picks), 1)
    each = round(equity_pct / n, 1)
    sleeves = []
    for p in picks:
        sleeves.append(
            {
                **p,
                "suggested_weight_pct": each,
                "note": f"Consider a sleeve in {p['name']} given observed 1Y realized vol of {p['volatility']}%. Potentially suitable for a {risk} stance — not a directive to buy.",
            }
        )
    text = (
        f"Evidence suggests a {risk} mix of about {equity_pct}% listed equities and {cash_pct}% cash/liquid reserves "
        f"for a {horizon} horizon with a {objective} objective. Available capital ₹{capital:,.0f}; monthly add ₹{monthly:,.0f}. "
        "Past volatility is not a guarantee of future risk. Trade-offs: higher equity weight increases drawdown risk; "
        "higher cash preserves capital but may lag inflation. FININT does not promise returns."
    )
    extra = None
    if llm_available():
        extra = complete(
            "Write cautious investment research. Ban: guaranteed, risk-free, definitely buy, stock will rise.",
            text,
            220,
        )
    return {
        "available": True,
        "equity_pct": equity_pct,
        "cash_pct": cash_pct,
        "sleeves": sleeves,
        "narrative": extra or text,
        "disclaimer": "FININT provides research and decision-support intelligence. It does not provide financial advice or guarantee investment outcomes.",
        "universe_failures": [r["symbol"] for r in ranked if not r["available"]],
    }


def chat(message: str, user_id: str = "local") -> dict[str, Any]:
    with db() as conn:
        rec = conn.execute(
            "SELECT * FROM recommendations WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        cites = []
        if rec:
            cites = [dict(x) for x in conn.execute(
                "SELECT source, title, url, snippet FROM citations WHERE run_id = ? LIMIT 8",
                (rec["run_id"],),
            ).fetchall()]
    context = {
        "last_recommendation": json.loads(rec["payload"]) if rec else None,
        "citations": cites,
        "question": message,
    }
    if not rec and "portfolio" not in message.lower():
        grounded = None
    else:
        grounded = json.dumps(context)[:8000]
    if llm_available() and grounded:
        answer = complete(
            "Answer using only provided JSON. If missing, reply INSUFFICIENT EVIDENCE. Cite source titles.",
            grounded,
            400,
        )
        if answer:
            return {"answer": answer, "sources": cites, "mode": "llm"}
    if rec:
        payload = json.loads(rec["payload"])
        syn = payload.get("synthesis") or {}
        action = syn.get("action") or rec["action"]
        return {
            "answer": (
                f"The latest FININT research signal on {payload.get('symbol')} is {action} "
                f"with confidence {rec['confidence']}%. "
                + (syn.get("thesis") or "")
                + " If you need a live recompute, run AI Analysis. This is not financial advice."
            ),
            "sources": cites,
            "mode": "structured",
        }
    return {
        "answer": "INSUFFICIENT EVIDENCE — no stored analysis yet. Run AI Analysis on a symbol first.",
        "sources": [],
        "mode": "empty",
    }
