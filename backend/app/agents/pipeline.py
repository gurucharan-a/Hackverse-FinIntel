from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.db import db, utcnow
from app.schemas import AgentResult, EvidenceItem
from app.services.confidence import compute_confidence
from app.services.data_providers.filing_provider import filing_provider
from app.services.data_providers.financial_provider import financial_provider
from app.services.data_providers.market_provider import display_symbol, market_provider, resolve_symbol
from app.services.data_providers.news_provider import news_provider
from app.services.indicators import compute_stack
from app.services.llm import complete, llm_available
from app.services.timeutil import iso_ist, now_ist
from app.rag.store import vector_store
from app.services.textutil import uid

FAILURE_LABELS = {
    "market": "MARKET DATA UNAVAILABLE",
    "news": "NEWS DATA UNAVAILABLE",
    "documents": "FINANCIAL DOCUMENT UNAVAILABLE",
    "technical": "TECHNICAL AGENT UNAVAILABLE",
    "fundamental": "FUNDAMENTAL AGENT UNAVAILABLE",
    "sentiment": "SENTIMENT AGENT UNAVAILABLE",
    "portfolio": "PORTFOLIO RISK AGENT UNAVAILABLE",
}


def _stamp() -> str:
    return now_ist().strftime("%H:%M:%S")


def _iso() -> str:
    return iso_ist(datetime.now(timezone.utc))


def load_profile(user_id: str = "local") -> dict[str, Any]:
    with db() as conn:
        p = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        holdings = conn.execute(
            "SELECT * FROM portfolio_holdings WHERE user_id = ?", (user_id,)
        ).fetchall()
    if not p:
        raise KeyError("profile")
    return {
        "user_id": user_id,
        "risk_tolerance": p["risk_tolerance"],
        "horizon": p["horizon"],
        "capital": p["capital"],
        "monthly_investment": p["monthly_investment"],
        "max_stock_allocation": p["max_stock_allocation"],
        "objective": p["objective"],
        "holdings": [dict(h) for h in holdings],
    }


def technical_agent(quote, history, fail: bool = False) -> AgentResult:
    t0 = time.perf_counter()
    started = _iso()
    if fail or not quote.available or not history.available or len(history.bars) < 20:
        return AgentResult(
            agent="technical",
            status="unavailable",
            signal="UNAVAILABLE",
            reasoning="Technical analysis unavailable because current market data could not be retrieved."
            if fail or not quote.available
            else "INSUFFICIENT EVIDENCE — fewer than 20 price bars available for indicators.",
            data_source=quote.meta.source if quote else None,
            started_at=started,
            finished_at=_iso(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            error=FAILURE_LABELS["technical"] if fail else "DATA UNAVAILABLE",
        )
    closes = [b.close for b in history.bars]
    volumes = [b.volume for b in history.bars]
    stack = compute_stack(closes, volumes)
    score = 0
    reasons = []
    rsi = stack["rsi"]
    if rsi is not None:
        if rsi >= 70:
            score -= 1
            reasons.append(f"RSI {rsi} is in overbought territory.")
        elif rsi <= 30:
            score += 1
            reasons.append(f"RSI {rsi} is in oversold territory.")
        elif rsi >= 55:
            score += 1
            reasons.append(f"RSI {rsi} indicates constructive momentum.")
        elif rsi <= 45:
            score -= 1
            reasons.append(f"RSI {rsi} indicates weakening momentum.")
        else:
            reasons.append(f"RSI {rsi} is balanced.")
    sma20, sma50 = stack["sma20"], stack["sma50"]
    px = quote.price
    if px and sma20:
        if px > sma20:
            score += 1
            reasons.append(f"Price {px:.2f} is above 20 DMA {sma20:.2f}.")
        else:
            score -= 1
            reasons.append(f"Price {px:.2f} is below 20 DMA {sma20:.2f}.")
    if sma20 and sma50:
        if sma20 > sma50:
            score += 1
            reasons.append("20 DMA is above 50 DMA (uptrend structure).")
        else:
            score -= 1
            reasons.append("20 DMA is below 50 DMA (downtrend structure).")
    macd = stack["macd"]
    if macd.get("hist") is not None:
        if macd["hist"] > 0:
            score += 1
            reasons.append(f"MACD histogram {macd['hist']} is positive.")
        else:
            score -= 1
            reasons.append(f"MACD histogram {macd['hist']} is negative.")
    if score >= 2:
        signal, risk = "BULLISH", "MEDIUM"
    elif score <= -2:
        signal, risk = "BEARISH", "MEDIUM"
    else:
        signal, risk = "NEUTRAL", "MEDIUM"
    if stack["volatility"] and stack["volatility"] > 40:
        risk = "HIGH"
        reasons.append(f"Realized volatility {stack['volatility']}% is elevated.")
    filled = sum(1 for k in ("rsi", "sma20", "sma50") if stack.get(k) is not None)
    conf = round(40 + filled * 15 + min(20, abs(score) * 8), 1)
    evidence = [
        EvidenceItem(
            id=uid("tech", quote.yahoo_symbol, "price"),
            source=quote.meta.source,
            title=f"{quote.symbol} last price {quote.price}",
            company=quote.symbol,
            category="MARKET",
            url=f"https://finance.yahoo.com/quote/{quote.yahoo_symbol}",
            snippet=f"Last {quote.price} change {quote.change_pct}% volume {quote.volume}.",
            agent="technical",
            relevance=1.0,
            timestamp=quote.meta.timestamp,
        )
    ]
    return AgentResult(
        agent="technical",
        status="ok",
        signal=signal,
        confidence=min(conf, 92),
        risk=risk,
        reasoning=" ".join(reasons) or "INSUFFICIENT EVIDENCE",
        metrics={k: v for k, v in stack.items() if k not in {"sma20_series", "sma50_series"}},
        evidence=evidence,
        data_source=quote.meta.source,
        started_at=started,
        finished_at=_iso(),
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


def fundamental_agent(quote, fail: bool = False) -> AgentResult:
    t0 = time.perf_counter()
    started = _iso()
    if fail:
        return AgentResult(
            agent="fundamental",
            status="unavailable",
            signal="UNAVAILABLE",
            reasoning="Fundamental analysis unavailable because financial documents could not be retrieved.",
            started_at=started,
            finished_at=_iso(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            error=FAILURE_LABELS["fundamental"],
        )
    fin = financial_provider.snapshot(quote.yahoo_symbol)
    filings = filing_provider.fetch(quote.yahoo_symbol)
    snippets = fin.get("snippets") or []
    summary = (fin.get("info_subset") or {}).get("longBusinessSummary")
    if summary:
        snippets.append(summary[:800])
    if snippets:
        ids = [uid("rag", quote.yahoo_symbol, str(i)) for i in range(len(snippets))]
        vector_store.upsert(
            ids,
            snippets,
            [{"symbol": quote.yahoo_symbol, "source": "financials"} for _ in snippets],
        )
    retrieved = vector_store.query(
        f"{quote.name or quote.symbol} revenue profit margins debt cash flow risks",
        n=5,
        where={"symbol": quote.yahoo_symbol},
    ) if snippets else []
    metrics = fin.get("metrics") or {}
    if not fin.get("available"):
        return AgentResult(
            agent="fundamental",
            status="unavailable",
            signal="INSUFFICIENT EVIDENCE",
            reasoning=fin.get("error") or "DATA UNAVAILABLE",
            metrics=metrics,
            evidence=[],
            data_source="Yahoo Finance",
            started_at=started,
            finished_at=_iso(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            error="DATA UNAVAILABLE",
        )
    score = 0
    reasons = []
    g = metrics.get("revenue_growth")
    if g is not None:
        if g > 5:
            score += 1
            reasons.append(f"Revenue growth {g}% is positive in the latest comparable periods.")
        elif g < -5:
            score -= 1
            reasons.append(f"Revenue declined {g}% versus the prior period.")
        else:
            reasons.append(f"Revenue growth {g}% is modest.")
    m = metrics.get("net_margin")
    if m is not None:
        if m > 10:
            score += 1
            reasons.append(f"Net margin {m}% is healthy.")
        elif m < 5:
            score -= 1
            reasons.append(f"Net margin {m}% is thin.")
    de = metrics.get("debt_to_equity")
    if de is not None:
        if de > 1.5:
            score -= 1
            reasons.append(f"Debt-to-equity {de} is elevated.")
            risk = "HIGH"
        else:
            reasons.append(f"Debt-to-equity {de} is moderate.")
    risk = "MEDIUM"
    if de is not None and de > 1.5:
        risk = "HIGH"
    if score >= 1:
        signal = "POSITIVE"
    elif score <= -1:
        signal = "NEGATIVE"
    else:
        signal = "MIXED"
    evidence = [EvidenceItem(**e) for e in fin.get("evidence") or []]
    for e in filings.get("evidence") or []:
        evidence.append(EvidenceItem(**e))
    for r in retrieved:
        evidence.append(
            EvidenceItem(
                id=r["id"],
                source=str(r["metadata"].get("source", "RAG")),
                title="Retrieved financial chunk",
                company=quote.symbol,
                category="FINANCIALS",
                snippet=r["text"][:400],
                agent="fundamental",
                relevance=r.get("relevance"),
                timestamp=_iso(),
            )
        )
    conf = round(45 + min(30, len(evidence) * 4) + min(15, abs(score) * 8), 1)
    return AgentResult(
        agent="fundamental",
        status="ok",
        signal=signal,
        confidence=min(conf, 90),
        risk=risk,
        reasoning=" ".join(reasons) or "Evidence retrieved from financial statements.",
        metrics=metrics,
        evidence=evidence[:12],
        data_source="Yahoo Finance" + (" + SEC EDGAR" if filings.get("available") else ""),
        started_at=started,
        finished_at=_iso(),
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


def sentiment_agent(quote, fail: bool = False) -> AgentResult:
    t0 = time.perf_counter()
    started = _iso()
    if fail:
        return AgentResult(
            agent="sentiment",
            status="unavailable",
            signal="UNAVAILABLE",
            reasoning="Sentiment analysis unavailable because news could not be retrieved.",
            started_at=started,
            finished_at=_iso(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            error=FAILURE_LABELS["news"],
        )
    items = news_provider.fetch(quote.yahoo_symbol, quote.name)
    if not items:
        return AgentResult(
            agent="sentiment",
            status="unavailable",
            signal="INSUFFICIENT EVIDENCE",
            reasoning="NEWS DATA UNAVAILABLE",
            started_at=started,
            finished_at=_iso(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            error="DATA UNAVAILABLE",
        )
    pos = sum(1 for i in items if i.sentiment == "positive")
    neg = sum(1 for i in items if i.sentiment == "negative")
    neu = len(items) - pos - neg
    if pos > neg + 1:
        signal = "POSITIVE"
    elif neg > pos + 1:
        signal = "NEGATIVE"
    else:
        signal = "MIXED"
    evidence = [
        EvidenceItem(
            id=i.id,
            source=i.publisher or (i.meta.source if i.meta else "News"),
            title=i.title,
            company=quote.symbol,
            category="NEWS",
            url=i.url,
            snippet=i.title,
            agent="sentiment",
            relevance=i.relevance,
            published_at=i.published_at,
            timestamp=i.meta.timestamp if i.meta else i.published_at,
        )
        for i in items
    ]
    conf = round(40 + min(40, len(items) * 4) + abs(pos - neg) * 3, 1)
    return AgentResult(
        agent="sentiment",
        status="ok",
        signal=signal,
        confidence=min(conf, 88),
        risk="MEDIUM",
        reasoning=f"Analyzed {len(items)} articles: {pos} positive, {neu} neutral/mixed, {neg} negative. Headline lexicon scoring only — not a forecast.",
        metrics={"news_analyzed": len(items), "positive": pos, "neutral": neu, "negative": neg},
        evidence=evidence,
        data_source=items[0].meta.source if items and items[0].meta else "News",
        started_at=started,
        finished_at=_iso(),
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


def portfolio_risk_agent(quote, profile: dict[str, Any], fail: bool = False) -> AgentResult:
    t0 = time.perf_counter()
    started = _iso()
    if fail:
        return AgentResult(
            agent="portfolio_risk",
            status="unavailable",
            signal="UNAVAILABLE",
            reasoning="Portfolio risk agent unavailable.",
            started_at=started,
            finished_at=_iso(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            error=FAILURE_LABELS["portfolio"],
        )
    holdings = profile["holdings"]
    max_alloc = float(profile["max_stock_allocation"] or 0.2)
    valued = []
    total = 0.0
    for h in holdings:
        q = market_provider.quote(h["yahoo_symbol"])
        px = q.price if q.available and q.price is not None else None
        if px is None:
            continue
        value = px * float(h["quantity"])
        total += value
        valued.append({**h, "price": px, "value": value, "sector": h.get("sector") or q.sector})
    if total <= 0:
        return AgentResult(
            agent="portfolio_risk",
            status="unavailable",
            signal="INSUFFICIENT EVIDENCE",
            reasoning="DATA UNAVAILABLE — holdings could not be marked to market.",
            started_at=started,
            finished_at=_iso(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            error="DATA UNAVAILABLE",
        )
    target = next((v for v in valued if v["yahoo_symbol"] == quote.yahoo_symbol), None)
    alloc = (target["value"] / total) if target else 0.0
    sectors: dict[str, float] = {}
    for v in valued:
        sec = v.get("sector") or "Unknown"
        sectors[sec] = sectors.get(sec, 0) + v["value"] / total
    hhi = sum((v["value"] / total) ** 2 for v in valued)
    reasons = []
    signal = "LOW"
    if alloc > max_alloc:
        signal = "HIGH"
        reasons.append(
            f"{quote.symbol} current allocation {alloc*100:.1f}% exceeds preferred maximum {max_alloc*100:.1f}%."
        )
    elif alloc > max_alloc * 0.8:
        signal = "MEDIUM"
        reasons.append(
            f"{quote.symbol} allocation {alloc*100:.1f}% is approaching the preferred maximum {max_alloc*100:.1f}%."
        )
    else:
        if target:
            reasons.append(
                f"{quote.symbol} allocation {alloc*100:.1f}% is within the preferred maximum {max_alloc*100:.1f}%."
            )
        else:
            reasons.append(f"{quote.symbol} is not currently held. Concentration risk from this name is incremental.")
    top_sector, top_w = max(sectors.items(), key=lambda x: x[1])
    if top_w > 0.45:
        if signal == "LOW":
            signal = "MEDIUM"
        reasons.append(f"Sector concentration: {top_sector} is {top_w*100:.1f}% of the book.")
    reasons.append(f"Portfolio HHI concentration index is {hhi:.3f} (1.0 = single name).")
    if profile["risk_tolerance"] == "conservative" and signal != "LOW":
        reasons.append("Conservative risk tolerance increases the weight of this concentration warning.")
    evidence = [
        EvidenceItem(
            id=uid("port", quote.yahoo_symbol),
            source="User portfolio + Yahoo Finance marks",
            title="Position sizing vs preferred maximum",
            company=quote.symbol,
            category="MARKET",
            snippet=reasons[0],
            agent="portfolio_risk",
            relevance=1.0,
            timestamp=_iso(),
        )
    ]
    conf = 70.0 if target else 55.0
    return AgentResult(
        agent="portfolio_risk",
        status="ok",
        signal=signal,
        confidence=conf,
        risk=signal,
        reasoning=" ".join(reasons),
        metrics={
            "allocation": round(alloc * 100, 2),
            "preferred_max": round(max_alloc * 100, 2),
            "hhi": round(hhi, 4),
            "sectors": {k: round(v * 100, 2) for k, v in sectors.items()},
            "held": bool(target),
            "portfolio_value": round(total, 2),
        },
        evidence=evidence,
        data_source="SQLite holdings + Yahoo Finance",
        started_at=started,
        finished_at=_iso(),
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


def detect_conflict(agents: list[AgentResult]) -> dict[str, Any]:
    mapping = {}
    for a in agents:
        if a.status != "ok":
            continue
        if a.agent == "portfolio_risk":
            mapping[a.agent] = {"HIGH": "BEARISH", "MEDIUM": "NEUTRAL", "LOW": "BULLISH"}.get(a.signal, "NEUTRAL")
        else:
            mapping[a.agent] = {
                "BULLISH": "BULLISH",
                "POSITIVE": "BULLISH",
                "BEARISH": "BEARISH",
                "NEGATIVE": "BEARISH",
                "NEUTRAL": "NEUTRAL",
                "MIXED": "NEUTRAL",
            }.get(a.signal, "NEUTRAL")
    sides = {k: v for k, v in mapping.items() if v in {"BULLISH", "BEARISH"}}
    bull = [k for k, v in sides.items() if v == "BULLISH"]
    bear = [k for k, v in sides.items() if v == "BEARISH"]
    detected = bool(bull) and bool(bear)
    penalty = 0
    why = "No material directional conflict among live agents."
    if detected:
        penalty = 8 + 4 * min(len(bull), len(bear))
        why = (
            f"{', '.join(bull)} lean constructive while {', '.join(bear)} lean cautious. "
            "Disagreement increases uncertainty and reduces final confidence."
        )
    return {"detected": detected, "mapping": mapping, "bull": bull, "bear": bear, "penalty": penalty, "explanation": why}


def synthesize(quote, profile: dict[str, Any], agents: list[AgentResult], conflict: dict[str, Any]) -> dict[str, Any]:
    risk = profile["risk_tolerance"]
    weights = {
        "conservative": {"technical": 0.15, "fundamental": 0.40, "sentiment": 0.15, "portfolio_risk": 0.30},
        "moderate": {"technical": 0.25, "fundamental": 0.30, "sentiment": 0.20, "portfolio_risk": 0.25},
        "aggressive": {"technical": 0.35, "fundamental": 0.20, "sentiment": 0.25, "portfolio_risk": 0.20},
    }.get(risk, {"technical": 0.25, "fundamental": 0.30, "sentiment": 0.20, "portfolio_risk": 0.25})

    score = 0.0
    used = 0.0
    for a in agents:
        if a.status != "ok":
            continue
        pol = conflict["mapping"].get(a.agent, "NEUTRAL")
        delta = {"BULLISH": 1, "BEARISH": -1}.get(pol, 0)
        w = weights.get(a.agent, 0.2)
        score += delta * w
        used += w
    if used == 0:
        action = "WATCH"
        thesis = "INSUFFICIENT DATA — no live agents produced usable signals."
    else:
        adj = score / used
        if adj > 0.35:
            action = "CONSIDER"
        elif adj < -0.35:
            action = "AVOID"
        else:
            action = "HOLD"
        if risk == "conservative" and action == "CONSIDER":
            port = next((x for x in agents if x.agent == "portfolio_risk"), None)
            if port and port.signal == "HIGH":
                action = "HOLD"
        thesis = (
            f"Profile={risk}, horizon={profile['horizon']}, objective={profile['objective']}. "
            f"Weighted directional score {adj:.2f} from live agents. "
            "This is an AI research signal, not financial advice."
        )
    conf = compute_confidence(agents, conflict)
    port = next((x for x in agents if x.agent == "portfolio_risk"), None)
    risk_label = port.signal if port and port.status == "ok" else "UNKNOWN"
    evidence_n = sum(len(a.evidence) for a in agents)
    news_n = next((a.metrics.get("news_analyzed", 0) for a in agents if a.agent == "sentiment"), 0)
    llm_note = None
    if llm_available():
        packed = json.dumps(
            {
                "action": action,
                "agents": [{"agent": a.agent, "signal": a.signal, "reasoning": a.reasoning} for a in agents],
                "conflict": conflict["explanation"],
            }
        )
        llm_note = complete(
            "You write cautious investment research notes for retail investors in India.",
            f"Summarize why the action is {action} using only: {packed}",
            280,
        )
    return {
        "action": action,
        "risk": risk_label if risk_label in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM",
        "confidence": conf,
        "thesis": llm_note or thesis,
        "weights": weights,
        "evidence_items": evidence_n,
        "news_articles": news_n,
        "agents_used": sum(1 for a in agents if a.status == "ok"),
        "timestamp": _iso(),
    }


def run_pipeline(
    symbol: str,
    user_id: str = "local",
    simulate_failure: str | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    profile_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ysym = resolve_symbol(symbol)
    profile = profile_override or load_profile(user_id)
    traces: list[dict[str, Any]] = []

    def emit(status: str, message: str, agent: str | None = None) -> None:
        ev = {"ts": _stamp(), "iso": _iso(), "status": status, "message": message, "agent": agent}
        traces.append(ev)
        if on_event:
            on_event(ev)

    emit("ok", f"Analysis started for {display_symbol(ysym)}")
    fail_market = simulate_failure == "market"
    quote = market_provider.quote(ysym)
    history = market_provider.history(ysym, "6M")
    if fail_market:
        quote.available = False
        quote.price = None
        quote.meta.freshness = "UNAVAILABLE"
        history.available = False
        history.bars = []
        emit("error", "MARKET DATA UNAVAILABLE")
    elif quote.available:
        emit("ok", "Market data retrieved")
    else:
        emit("error", "MARKET DATA UNAVAILABLE")

    tech = fund = sent = port = None
    emit("ok", "Technical Agent started", "technical")
    tech = technical_agent(quote, history, fail=simulate_failure in {"technical", "market"})
    emit("ok" if tech.status == "ok" else "error", "Technical Agent completed" if tech.status == "ok" else "TECHNICAL AGENT UNAVAILABLE", "technical")

    emit("ok", "Fundamental Agent started", "fundamental")
    fund = fundamental_agent(quote, fail=simulate_failure in {"documents", "fundamental"})
    if fund.status == "ok":
        emit("ok", "Documents retrieved", "fundamental")
        emit("ok", "Fundamental Agent completed", "fundamental")
    else:
        emit("error", fund.error or "FUNDAMENTAL AGENT UNAVAILABLE", "fundamental")

    emit("ok", "Sentiment Agent started", "sentiment")
    sent = sentiment_agent(quote, fail=simulate_failure == "news")
    emit("ok" if sent.status == "ok" else "error", "Sentiment Agent completed" if sent.status == "ok" else "NEWS DATA UNAVAILABLE", "sentiment")

    emit("ok", "Portfolio Risk Agent started", "portfolio_risk")
    port = portfolio_risk_agent(quote, profile, fail=simulate_failure == "portfolio")
    emit("ok" if port.status == "ok" else "error", "Portfolio Risk Agent completed" if port.status == "ok" else "PORTFOLIO RISK AGENT UNAVAILABLE", "portfolio_risk")

    agents = [tech, fund, sent, port]
    conflict = detect_conflict(agents)
    emit("ok", "Conflict detector completed")
    if conflict["detected"]:
        emit("warn", "CONFLICT DETECTED")
    rec = synthesize(quote, profile, agents, conflict)
    rec = {**rec, "confidence": rec["confidence"].model_dump()}
    emit("ok", "Synthesis Agent completed")
    emit("ok", "Recommendation generated")

    run_id = uid("run", ysym, rec["timestamp"])
    _persist_run(run_id, user_id, ysym, simulate_failure, traces, agents, rec, quote)
    from app.services.indicators import rsi as rsi_fn, last_value

    closes = [b.close for b in history.bars]
    header_metrics = {
        "rsi": rsi_fn(closes) if closes else None,
        "dma20": tech.metrics.get("sma20") if tech.status == "ok" else None,
        "dma50": tech.metrics.get("sma50") if tech.status == "ok" else None,
        "volatility": tech.metrics.get("volatility") if tech.status == "ok" else None,
    }
    return {
        "run_id": run_id,
        "symbol": display_symbol(ysym),
        "yahoo_symbol": ysym,
        "quote": quote.model_dump(),
        "history_meta": history.meta.model_dump(),
        "header_metrics": header_metrics,
        "agents": [a.model_dump() for a in agents],
        "conflict": conflict,
        "synthesis": rec,
        "trace": traces,
        "profile": {
            "risk_tolerance": profile["risk_tolerance"],
            "horizon": profile["horizon"],
            "objective": profile["objective"],
            "max_stock_allocation": profile["max_stock_allocation"],
        },
        "disclaimer": "FININT provides research and decision-support intelligence. It does not provide financial advice or guarantee investment outcomes.",
        "llm_used": llm_available(),
        "simulate_failure": simulate_failure,
    }


def _persist_run(run_id, user_id, ysym, sim, traces, agents, rec, quote) -> None:
    import json

    with db() as conn:
        conn.execute(
            """INSERT INTO agent_runs (id, user_id, yahoo_symbol, started_at, finished_at, status, simulate_failure, trace)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, user_id, ysym, traces[0]["iso"] if traces else utcnow(), utcnow(), "complete", sim, json.dumps(traces)),
        )
        for a in agents:
            conn.execute(
                """INSERT INTO agent_outputs (run_id, agent, payload, latency_ms, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, a.agent, a.model_dump_json(), a.latency_ms, a.status),
            )
            for e in a.evidence:
                conn.execute(
                    """INSERT INTO citations (run_id, agent, source, title, url, snippet, published_at, relevance, page)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, a.agent, e.source, e.title, e.url, e.snippet, e.published_at, e.relevance, e.page),
                )
        conn.execute(
            """INSERT INTO recommendations (id, run_id, user_id, yahoo_symbol, action, confidence, risk, payload, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uid("rec", run_id),
                run_id,
                user_id,
                ysym,
                rec["action"],
                rec["confidence"].final,
                rec["risk"],
                json.dumps({"synthesis": rec, "symbol": display_symbol(ysym)}),
                utcnow(),
            ),
        )
        for a in agents:
            if a.latency_ms is not None:
                conn.execute(
                    """INSERT INTO performance_metrics (run_id, name, value, unit, recorded_at, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (run_id, f"latency_{a.agent}", a.latency_ms, "ms", utcnow(), None),
                )
        conn.execute(
            """INSERT INTO performance_metrics (run_id, name, value, unit, recorded_at, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, "agent_agreement", rec["confidence"].agent_agreement, "score", utcnow(), None),
        )
        conn.execute(
            """INSERT INTO performance_metrics (run_id, name, value, unit, recorded_at, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, "evidence_items", rec["evidence_items"], "count", utcnow(), None),
        )
