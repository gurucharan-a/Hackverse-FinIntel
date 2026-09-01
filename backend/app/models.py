from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Stance = Literal["bullish", "bearish", "neutral", "abstain"]
SignalLabel = Literal[
    "strong_buy_pressure",
    "buy_pressure",
    "neutral",
    "sell_pressure",
    "strong_sell_pressure",
    "conflicting",
    "unavailable",
]
Action = Literal["add", "hold", "trim", "avoid", "watch"]


class Citation(BaseModel):
    source_id: str
    title: str
    excerpt: str
    as_of: str
    score: float | None = None


class DimensionSignal(BaseModel):
    dimension: str
    label: SignalLabel
    score: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    citations: list[Citation] = Field(default_factory=list)
    degraded: bool = False


class AgentOutput(BaseModel):
    agent_id: str
    role: str
    stance: Stance
    confidence: float = Field(ge=0, le=1)
    thesis: str
    key_facts: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    degraded: bool = False
    degradation_reason: str | None = None
    latency_ms: float = 0
    weight_applied: float | None = None


class MarketTick(BaseModel):
    symbol: str
    name: str
    last: float
    change_pct: float
    volume: int
    avg_volume_20d: int
    rsi_14: float
    momentum_20d: float
    vwap_dev_pct: float
    fii_net_cr: float
    put_call_ratio: float
    sector: str
    as_of: datetime
    feed_status: Literal["live", "simulated", "degraded"] = "simulated"


class Holding(BaseModel):
    symbol: str
    qty: int
    avg_cost: float
    last: float | None = None


class UserProfile(BaseModel):
    user_id: str
    name: str
    age: int
    risk_tolerance: Literal["conservative", "balanced", "aggressive"]
    horizon_years: int
    fno_allowed: bool
    max_single_name_pct: float
    behavioral_flags: list[str] = Field(default_factory=list)
    watchlist: list[str]
    holdings: list[Holding]


class Recommendation(BaseModel):
    action: Action
    symbol: str
    headline: str
    rationale: str
    confidence: float
    personalization_notes: list[str]
    citations: list[Citation]
    conflicts: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)


class SessionMetrics(BaseModel):
    session_id: str
    symbol: str
    user_id: str
    agent_response_latency_ms: float
    signal_accuracy_proxy: float | None
    portfolio_risk_concentration: float
    degraded_agents: int
    timestamp: datetime


class AnalysisResponse(BaseModel):
    session_id: str
    generated_at: datetime
    tick: MarketTick
    signals: list[DimensionSignal]
    agents: list[AgentOutput]
    recommendation: Recommendation
    portfolio: list[Holding]
    metrics: SessionMetrics
    reasoning_chain: list[str]
    scenario: str
