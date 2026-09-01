from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Freshness = Literal["REAL-TIME", "NEAR REAL-TIME", "DELAYED", "HISTORICAL", "UNAVAILABLE"]
AgentStatus = Literal["ok", "unavailable", "degraded", "skipped"]


class DataMeta(BaseModel):
    source: str
    provider: str
    timestamp: str | None = None
    freshness: Freshness = "UNAVAILABLE"


class Quote(BaseModel):
    symbol: str
    yahoo_symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str = "INR"
    price: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    market_cap: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    sector: str | None = None
    industry: str | None = None
    available: bool = False
    meta: DataMeta


class Bar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class History(BaseModel):
    yahoo_symbol: str
    range: str
    interval: str
    bars: list[Bar] = Field(default_factory=list)
    sma20: list[float | None] = Field(default_factory=list)
    sma50: list[float | None] = Field(default_factory=list)
    available: bool = False
    meta: DataMeta


class NewsItem(BaseModel):
    id: str
    title: str
    publisher: str | None = None
    url: str | None = None
    published_at: str | None = None
    sentiment: str | None = None
    relevance: float | None = None
    yahoo_symbol: str | None = None
    available: bool = True
    meta: DataMeta | None = None


class EvidenceItem(BaseModel):
    id: str | None = None
    source: str
    title: str
    company: str | None = None
    category: str
    url: str | None = None
    page: int | None = None
    snippet: str | None = None
    agent: str | None = None
    relevance: float | None = None
    published_at: str | None = None
    timestamp: str | None = None


class AgentResult(BaseModel):
    agent: str
    status: AgentStatus
    signal: str
    confidence: float | None = None
    risk: str | None = None
    reasoning: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    data_source: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    latency_ms: float | None = None
    error: str | None = None


class ConfidenceBreakdown(BaseModel):
    base: float
    agent_agreement: float
    data_completeness: float
    evidence_quality: float
    data_freshness: float
    signal_strength: float
    conflict_adjustment: float
    missing_data_adjustment: float
    final: float
    notes: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    ts: str
    status: str
    message: str
    agent: str | None = None
