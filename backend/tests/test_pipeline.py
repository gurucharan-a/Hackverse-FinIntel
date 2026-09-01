from __future__ import annotations

from app.orchestrator import run_analysis
from app.profiles import USERS


def test_three_agents_parallel_contract():
    out = run_analysis("RELIANCE", "priya", "base")
    ids = {a.agent_id for a in out.agents}
    assert ids == {"technical", "fundamental", "sentiment"}
    for a in out.agents:
        assert a.thesis
        assert 0 <= a.confidence <= 1
        if not a.degraded:
            assert a.citations, "non-degraded agents must cite"


def test_signals_three_dimensions():
    out = run_analysis("RELIANCE", "meera", "base")
    dims = {s.dimension for s in out.signals}
    assert dims == {"price_momentum", "volume_anomaly", "sentiment"}
    assert all(s.reasoning for s in out.signals)


def test_profiles_diverge_on_identical_tape():
    priya = run_analysis("ZOMATO", "priya", "base")
    arjun = run_analysis("ZOMATO", "arjun", "base")
    assert priya.tick.symbol == arjun.tick.symbol
    assert priya.recommendation.action != arjun.recommendation.action or (
        priya.recommendation.headline != arjun.recommendation.headline
    )
    assert priya.recommendation.personalization_notes != arjun.recommendation.personalization_notes


def test_missing_filing_no_uncited_fundamental():
    out = run_analysis("PAYTM", "meera", "missing_filing")
    fund = next(a for a in out.agents if a.agent_id == "fundamental")
    assert fund.degraded
    assert fund.stance == "abstain"
    assert fund.citations == []
    assert out.recommendation.citations, "synthesis still cites other agents"


def test_feed_down_does_not_crash():
    out = run_analysis("HDFCBANK", "priya", "feed_down")
    assert out.tick.feed_status == "degraded"
    tech = next(a for a in out.agents if a.agent_id == "technical")
    assert tech.stance == "abstain"
    assert out.recommendation.action in {"hold", "watch", "avoid", "trim"}
    assert "degraded_feed" in out.recommendation.safety_flags


def test_conflict_scenario_surfaces_disagreement():
    out = run_analysis("ZOMATO", "meera", "conflict")
    stances = {a.stance for a in out.agents if not a.degraded}
    assert "bullish" in stances or "bearish" in stances
    assert out.recommendation.confidence <= 0.52 or out.recommendation.conflicts or out.recommendation.action in {
        "watch",
        "hold",
        "trim",
        "avoid",
    }


def test_metrics_logged():
    out = run_analysis("INFY", "priya", "base")
    m = out.metrics
    assert m.agent_response_latency_ms >= 0
    assert m.portfolio_risk_concentration > 0
    assert m.signal_accuracy_proxy in (0.0, 1.0)
    assert m.session_id
