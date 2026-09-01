from __future__ import annotations

from app.schemas import AgentResult, ConfidenceBreakdown
from app.services.textutil import clamp

UNAVAILABLE_SIGNALS = {"UNAVAILABLE", "INSUFFICIENT EVIDENCE", "SKIPPED", ""}


def compute_confidence(agents: list[AgentResult], conflict: dict) -> ConfidenceBreakdown:
    live = [a for a in agents if a.status == "ok" and a.signal not in UNAVAILABLE_SIGNALS]
    missing = [a for a in agents if a.status != "ok" or a.signal in UNAVAILABLE_SIGNALS]
    notes: list[str] = []

    base = 42.0
    notes.append("Base 42 reflects starting uncertainty before evidence is scored.")

    if len(live) >= 2:
        polarities = [_polarity(a.signal) for a in live]
        polarities = [p for p in polarities if p != 0]
        if polarities:
            agree = abs(sum(polarities)) / (len(polarities) or 1)
            agent_agreement = round(18 * agree, 2)
        else:
            agent_agreement = 6.0
    else:
        agent_agreement = 0.0
        notes.append("Fewer than two live agents; agreement contribution is 0.")

    expected = 4
    data_completeness = round(15 * (len(live) / expected), 2)

    evidence_n = sum(len(a.evidence) for a in live)
    evidence_quality = round(min(16.0, evidence_n * 1.6), 2)

    freshness_hits = 0
    freshness_total = 0
    for a in agents:
        src = (a.data_source or "").lower()
        freshness_total += 1
        if a.status == "ok":
            freshness_hits += 1
    data_freshness = round(10 * (freshness_hits / max(freshness_total, 1)), 2)

    strengths = [a.confidence for a in live if a.confidence is not None]
    signal_strength = round((sum(strengths) / len(strengths) / 100) * 12, 2) if strengths else 0.0

    conflict_adjustment = 0.0
    if conflict.get("detected"):
        conflict_adjustment = -float(conflict.get("penalty", 12))
        notes.append("Conflict among agents reduced confidence.")

    missing_data_adjustment = round(-8.0 * len(missing), 2)
    if missing:
        notes.append("Missing-data penalty applied for unavailable agents: " + ", ".join(a.agent for a in missing))

    final = clamp(
        base
        + agent_agreement
        + data_completeness
        + evidence_quality
        + data_freshness
        + signal_strength
        + conflict_adjustment
        + missing_data_adjustment
    )
    notes.append(
        "Confidence reflects evidence quality, data freshness, agent agreement and uncertainty. "
        "It is NOT the probability that the recommendation will be correct."
    )
    return ConfidenceBreakdown(
        base=base,
        agent_agreement=agent_agreement,
        data_completeness=data_completeness,
        evidence_quality=evidence_quality,
        data_freshness=data_freshness,
        signal_strength=signal_strength,
        conflict_adjustment=conflict_adjustment,
        missing_data_adjustment=missing_data_adjustment,
        final=round(final, 1),
        notes=notes,
    )


def _polarity(signal: str) -> int:
    s = (signal or "").upper()
    if s in {"BULLISH", "POSITIVE", "CONSIDER", "ADD", "LOW"}:
        return 1
    if s in {"BEARISH", "NEGATIVE", "AVOID", "TRIM", "HIGH"}:
        return -1
    return 0
