from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app import sessionlog
from app.agents import AGENTS
from app.market import UNIVERSE, all_ticks, forward_return, snapshot
from app.market.signals import classify
from app.models import AnalysisResponse, Holding, SessionMetrics
from app.profiles import get_user
from app.synthesis import herfindahl, synthesize

SCENARIOS = {
    "base": "Healthy feeds and full filing corpus.",
    "feed_down": "Price/volume feed unavailable for the selected symbol.",
    "missing_filing": "Symbol-specific filings dropped from retrieval.",
    "conflict": "Forces the conflict path by analysing ZOMATO (hot tape vs weak filings).",
}


def run_analysis(symbol: str, user_id: str, scenario: str = "base") -> AnalysisResponse:
    symbol = symbol.upper()
    if scenario == "conflict":
        symbol = "ZOMATO"
    if symbol not in UNIVERSE:
        raise KeyError(symbol)

    user = get_user(user_id)
    feed_down = scenario == "feed_down"
    tick = snapshot(symbol, feed_down=feed_down)
    signals = classify(tick)

    drop_ids: set[str] = set()
    if scenario == "missing_filing":
        drop_ids = {d["id"] for d in __import__("app.rag.corpus", fromlist=["CORPUS"]).CORPUS if d["symbol"] == symbol}

    def _run(agent):
        return agent.run(tick, user, drop_doc_ids=drop_ids)

    t0 = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=3) as pool:
        agents = list(pool.map(_run, AGENTS))
    rec, chain, agents = synthesize(tick, user, agents)

    last_map = {t.symbol: t.last for t in all_ticks()}
    holdings: list[Holding] = []
    for h in user.holdings:
        px = last_map.get(h.symbol, h.avg_cost)
        holdings.append(h.model_copy(update={"last": px}))

    # Signal accuracy proxy: did composite score sign match 30d forward return?
    composite = sum(s.score * s.confidence for s in signals)
    fwd = forward_return(symbol)
    if tick.feed_status == "degraded":
        acc = None
    else:
        acc = 1.0 if (composite == 0 and abs(fwd) < 0.02) or (composite * fwd > 0) else 0.0

    conc = herfindahl(holdings, {h.symbol: h.last or h.avg_cost for h in holdings})
    latency = sum(a.latency_ms for a in agents)  # parallel wall time ~ max, report max
    wall = max(a.latency_ms for a in agents) if agents else 0.0

    metrics = SessionMetrics(
        session_id=str(uuid.uuid4())[:8],
        symbol=symbol,
        user_id=user.user_id,
        agent_response_latency_ms=round(wall, 2),
        signal_accuracy_proxy=acc,
        portfolio_risk_concentration=conc,
        degraded_agents=sum(1 for a in agents if a.degraded),
        timestamp=datetime.now(timezone.utc),
    )
    sessionlog.persist(metrics)

    chain.insert(0, f"Scenario={scenario}: {SCENARIOS.get(scenario, scenario)}")
    chain.insert(1, f"Ingested tape for {symbol} at {tick.last} ({tick.feed_status}).")
    chain.append(f"Logged metrics session={metrics.session_id} latency_ms={wall:.1f} HHI={conc}.")

    return AnalysisResponse(
        session_id=metrics.session_id,
        generated_at=t0,
        tick=tick,
        signals=signals,
        agents=agents,
        recommendation=rec,
        portfolio=holdings,
        metrics=metrics,
        reasoning_chain=chain,
        scenario=scenario,
    )
