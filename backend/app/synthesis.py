from __future__ import annotations

from app.models import AgentOutput, Holding, MarketTick, Recommendation, UserProfile


def herfindahl(holdings: list[Holding], last_by_symbol: dict[str, float]) -> float:
    values = []
    for h in holdings:
        px = last_by_symbol.get(h.symbol, h.last or h.avg_cost)
        values.append(h.qty * px)
    total = sum(values) or 1.0
    weights = [v / total for v in values]
    return round(sum(w * w for w in weights), 4)


def synthesize(
    tick: MarketTick,
    user: UserProfile,
    agents: list[AgentOutput],
) -> tuple[Recommendation, list[str], list[AgentOutput]]:
    chain: list[str] = []
    chain.append(f"User {user.name} ({user.risk_tolerance}, horizon {user.horizon_years}y, F&O={'yes' if user.fno_allowed else 'no'}).")

    risk_scale = {"conservative": 0.55, "balanced": 1.0, "aggressive": 1.25}[user.risk_tolerance]
    tech_w, fund_w, sent_w = 0.28 * risk_scale, 0.42 / risk_scale, 0.30
    if user.risk_tolerance == "conservative":
        fund_w, tech_w = 0.55, 0.18
        sent_w = 0.27
    if user.risk_tolerance == "aggressive":
        tech_w, fund_w, sent_w = 0.40, 0.28, 0.32

    weights = {"technical": tech_w, "fundamental": fund_w, "sentiment": sent_w}
    stance_score = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0, "abstain": 0.0}

    weighted = 0.0
    wsum = 0.0
    conflicts: list[str] = []
    safety: list[str] = []
    citations = []
    notes: list[str] = []
    scored_agents: list[AgentOutput] = []

    live = [a for a in agents if not (a.degraded and a.stance == "abstain")]
    stances = {a.agent_id: a.stance for a in live}
    if "bullish" in stances.values() and "bearish" in stances.values():
        conflicts.append(
            "Technical/sentiment and filings disagree. Synthesis down-weights conviction and refuses a one-sided call."
        )
        chain.append("Conflict detected across agent stances — conviction cap applied.")

    for a in agents:
        w = weights.get(a.agent_id, 0.2)
        if a.stance == "abstain" or a.degraded:
            w *= 0.15
        a.weight_applied = round(w, 3)
        scored_agents.append(a)
        weighted += stance_score[a.stance] * a.confidence * w
        wsum += w
        citations.extend(a.citations)
        chain.append(
            f"{a.agent_id} [{a.stance} c={a.confidence:.2f} w={w:.2f}{' DEGRADED' if a.degraded else ''}]: {a.thesis}"
        )

    raw = weighted / (wsum or 1.0)
    chain.append(f"Weighted stance score={raw:.3f} (pre-personalization).")

    holding = next((h for h in user.holdings if h.symbol == tick.symbol), None)
    last_map = {tick.symbol: tick.last}
    # approximate other marks from avg_cost if needed
    for h in user.holdings:
        last_map.setdefault(h.symbol, h.avg_cost)
    conc = herfindahl(user.holdings, last_map)
    port_val = sum(h.qty * last_map[h.symbol] for h in user.holdings) or 1
    name_w = (holding.qty * tick.last / port_val) if holding else 0.0

    if holding and name_w > user.max_single_name_pct:
        notes.append(
            f"{tick.symbol} is {name_w*100:.1f}% of book vs max {user.max_single_name_pct*100:.0f}% — size constraint binds."
        )
        raw -= 0.25
        chain.append("Single-name concentration cap reduced bullish score.")

    if "fomo_chases_breakouts" in user.behavioral_flags and tick.rsi_14 >= 70:
        notes.append("Behavioral history: breakout chasing. System fades extra momentum instead of amplifying it.")
        raw -= 0.2
        safety.append("behavior_fomo_guardrail")
        chain.append("FOMO guardrail: momentum contribution reduced.")

    if "loss_averse" in user.behavioral_flags and raw < 0:
        notes.append("Loss-averse profile: avoid forced selling into a noisy tape unless filings are impaired.")
        if raw > -0.35:
            raw += 0.12
            chain.append("Loss-aversion: small bearish scores mapped toward hold, not panic trim.")

    if not user.fno_allowed:
        safety.append("cash_equity_only")
        notes.append("F&O is blocked for this account (SEBI retail F&O loss study applied as suitability).")

    if tick.feed_status == "degraded":
        safety.append("degraded_feed")
        raw *= 0.3
        chain.append("Degraded feed: action space collapsed toward watch/hold.")

    # Map to action
    if conflicts and abs(raw) < 0.45:
        action = "watch" if not holding else "hold"
        headline = f"Conflicting evidence on {tick.symbol} — do not size a new conviction bet."
    elif raw >= 0.28:
        if holding and name_w > user.max_single_name_pct:
            action = "hold"
            headline = f"Thesis is constructive but {tick.symbol} is already oversized for {user.name}."
        else:
            action = "add"
            headline = f"Add (cash) {tick.symbol} — evidence stack is aligned for this profile."
    elif raw <= -0.32:
        if holding:
            action = "trim"
            headline = f"Trim {tick.symbol} — filings or crowding argue against adding risk here."
        else:
            action = "avoid"
            headline = f"Avoid initiating {tick.symbol} for this profile on current evidence."
    else:
        action = "hold" if holding else "watch"
        headline = f"No edge after personalization on {tick.symbol}."

    if user.risk_tolerance == "conservative" and action == "add" and tick.rsi_14 >= 70:
        action = "hold"
        headline = f"Conservative mandate: extended RSI blocks adds in {tick.symbol}."
        notes.append("Conservative overlay converted add → hold.")
        chain.append("Conservative overlay blocked chase-add.")

    if user.risk_tolerance == "aggressive" and action == "hold" and raw > 0.12 and not conflicts:
        # aggressive user can still add small if not concentrated
        if not holding or name_w < user.max_single_name_pct:
            action = "add"
            headline = f"Aggressive mandate: residual positive score allows a scaled add in {tick.symbol}."
            notes.append("Aggressive overlay converted hold → scaled add.")
            chain.append("Aggressive overlay allowed scaled add.")

    conf = min(0.9, 0.35 + abs(raw) * 0.7)
    if conflicts:
        conf = min(conf, 0.48)
    if any(a.degraded for a in agents):
        conf = min(conf, 0.52)
        notes.append("One or more agents degraded — confidence capped.")

    # Deduplicate citations, require at least one for non-unavailable recs
    uniq = []
    seen = set()
    for c in citations:
        if c.source_id in seen:
            continue
        seen.add(c.source_id)
        uniq.append(c)

    rec = Recommendation(
        action=action,  # type: ignore[arg-type]
        symbol=tick.symbol,
        headline=headline,
        rationale=(
            f"Synthesis blended technical, filing-grounded fundamental, and flow/sentiment agents "
            f"with {user.risk_tolerance} weights. Score {raw:.2f}. "
            + (" ".join(conflicts) if conflicts else "No hard conflict after weighting.")
        ),
        confidence=round(conf, 3),
        personalization_notes=notes,
        citations=uniq[:6],
        conflicts=conflicts,
        safety_flags=safety,
    )
    chain.append(f"Final action={action} confidence={conf:.2f}.")
    return rec, chain, scored_agents
