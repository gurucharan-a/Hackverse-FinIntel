from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.models import AgentOutput, Citation, MarketTick, UserProfile
from app.rag import INDEX


class Agent(ABC):
    agent_id: str
    role: str

    @abstractmethod
    def run(
        self,
        tick: MarketTick,
        user: UserProfile,
        *,
        drop_doc_ids: set[str] | None = None,
    ) -> AgentOutput:
        ...

    def _timed(self, fn) -> AgentOutput:  # type: ignore[no-untyped-def]
        t0 = time.perf_counter()
        out: AgentOutput = fn()
        out.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return out


def _tape_cite(tick: MarketTick) -> Citation:
    return Citation(
        source_id=f"feed:{tick.symbol}",
        title=f"{tick.symbol} simulated NSE tape ({tick.feed_status})",
        excerpt=(
            f"Last {tick.last:.2f} ({tick.change_pct:+.2f}%), RSI {tick.rsi_14:.1f}, "
            f"20d momentum {tick.momentum_20d * 100:.1f}%, volume {tick.volume:,}."
        ),
        as_of=tick.as_of.isoformat(),
        score=1.0,
    )


class TechnicalAgent(Agent):
    agent_id = "technical"
    role = "Price momentum & volume structure"

    def run(self, tick: MarketTick, user: UserProfile, *, drop_doc_ids: set[str] | None = None) -> AgentOutput:
        def inner() -> AgentOutput:
            if tick.feed_status == "degraded":
                return AgentOutput(
                    agent_id=self.agent_id,
                    role=self.role,
                    stance="abstain",
                    confidence=0.0,
                    thesis="Market feed is degraded. Technical agent abstains rather than interpolate a tape.",
                    key_facts=["feed_status=degraded"],
                    citations=[],
                    degraded=True,
                    degradation_reason="unavailable_price_feed",
                )
            rsi = tick.rsi_14
            mom = tick.momentum_20d
            vol_ratio = tick.volume / max(tick.avg_volume_20d, 1)
            if rsi >= 72 and vol_ratio >= 2:
                stance, conf = "bearish", 0.62
                thesis = (
                    "Momentum is extended (RSI ≥ 72) on a volume spike. For a swing horizon this is "
                    "chase-risk, not a fresh trend initiation."
                )
            elif mom > 0.04 and rsi < 70:
                stance, conf = "bullish", 0.71
                thesis = "Positive 20-day momentum with RSI still below overbought supports a constructive tactical bias."
            elif mom < -0.04:
                stance, conf = "bearish", 0.66
                thesis = "Negative 20-day momentum; dips are not yet confirmed as a reversal."
            else:
                stance, conf = "neutral", 0.58
                thesis = "Range-bound tape. No technical edge large enough to override fundamentals."
            return AgentOutput(
                agent_id=self.agent_id,
                role=self.role,
                stance=stance,  # type: ignore[arg-type]
                confidence=conf,
                thesis=thesis,
                key_facts=[f"RSI-14={rsi:.1f}", f"mom20={mom*100:.1f}%", f"vol_x={vol_ratio:.2f}"],
                citations=[_tape_cite(tick)],
            )

        return self._timed(inner)


class FundamentalAgent(Agent):
    agent_id = "fundamental"
    role = "Filings & earnings RAG"

    def run(self, tick: MarketTick, user: UserProfile, *, drop_doc_ids: set[str] | None = None) -> AgentOutput:
        def inner() -> AgentOutput:
            query = (
                f"{tick.symbol} {tick.name} earnings margin guidance promoter filing NPA "
                f"risk cash burn unit economics"
            )
            cites = INDEX.search(
                query, symbol=tick.symbol, k=3, drop_ids=drop_doc_ids, include_macro=False
            )
            if not cites:
                return AgentOutput(
                    agent_id=self.agent_id,
                    role=self.role,
                    stance="abstain",
                    confidence=0.0,
                    thesis=(
                        f"No filing or transcript chunk retrieved for {tick.symbol}. "
                        "Fundamental agent abstains — will not emit an uncited view."
                    ),
                    key_facts=["rag_miss"],
                    citations=[],
                    degraded=True,
                    degradation_reason="missing_filing",
                )
            blob = " ".join(c.excerpt.lower() + c.title.lower() for c in cites)
            bear_hits = sum(
                w in blob
                for w in [
                    "compressed",
                    "overhang",
                    "emphasis of matter",
                    "cash burn",
                    "negative",
                    "sale of up to",
                ]
            )
            bull_hits = sum(
                w in blob
                for w in ["expanded", "rose", "stable", "unmodified", "cet1", "retained"]
            )
            if bear_hits >= 2 and bear_hits > bull_hits:
                stance, conf = "bearish", 0.74
                thesis = (
                    "Retrieved disclosures emphasize margin pressure, supply overhang, or audit caveats. "
                    "Fundamental quality is not confirming the tape."
                )
            elif bull_hits >= 2:
                stance, conf = "bullish", 0.7
                thesis = (
                    "Retrieved earnings/filings show stable capital, clean audit language, or improving operating metrics."
                )
            else:
                stance, conf = "neutral", 0.6
                thesis = "Filings are mixed or descriptive. No single fundamental catalyst dominates."
            return AgentOutput(
                agent_id=self.agent_id,
                role=self.role,
                stance=stance,  # type: ignore[arg-type]
                confidence=conf,
                thesis=thesis,
                key_facts=[f"docs={len(cites)}", f"bear_hits={bear_hits}", f"bull_hits={bull_hits}"],
                citations=cites,
            )

        return self._timed(inner)


class SentimentAgent(Agent):
    agent_id = "sentiment"
    role = "FII flows, options crowding, macro"

    def run(self, tick: MarketTick, user: UserProfile, *, drop_doc_ids: set[str] | None = None) -> AgentOutput:
        def inner() -> AgentOutput:
            cites = INDEX.search(
                f"FII flows {tick.symbol} {tick.sector} retail F&O SEBI provisional",
                symbol=tick.symbol,
                k=2,
                drop_ids=drop_doc_ids,
            )
            if tick.feed_status == "degraded":
                return AgentOutput(
                    agent_id=self.agent_id,
                    role=self.role,
                    stance="neutral",
                    confidence=0.35,
                    thesis=(
                        "Name-level tape is down. Sentiment falls back to the macro FII provisional print, "
                        "which is not a name-specific recommendation."
                    ),
                    key_facts=["name_feed_degraded"],
                    citations=cites,
                    degraded=True,
                    degradation_reason="unavailable_price_feed",
                )
            pcr = tick.put_call_ratio
            fii = tick.fii_net_cr
            if pcr < 0.65:
                stance, conf = "bearish", 0.64
                thesis = (
                    f"Options PCR {pcr:.2f} signals crowded calls. Combined with a sharp print, "
                    "sentiment is hot and fragile rather than under-owned."
                )
            elif fii > 400:
                stance, conf = "bullish", 0.68
                thesis = f"Name-level FII net ₹{fii:.0f} Cr is a genuine demand signal in cash."
            elif fii < -80:
                stance, conf = "bearish", 0.6
                thesis = f"FII net ₹{fii:.0f} Cr — institutional cash is not supporting the name today."
            else:
                stance, conf = "neutral", 0.55
                thesis = "Flows and options skew are moderate. Sentiment is not the deciding vote."
            return AgentOutput(
                agent_id=self.agent_id,
                role=self.role,
                stance=stance,  # type: ignore[arg-type]
                confidence=conf,
                thesis=thesis,
                key_facts=[f"FII={fii:.0f}Cr", f"PCR={pcr:.2f}"],
                citations=cites or [_tape_cite(tick)],
            )

        return self._timed(inner)


AGENTS: list[Agent] = [TechnicalAgent(), FundamentalAgent(), SentimentAgent()]
