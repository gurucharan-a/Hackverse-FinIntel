# FinIntel — Multi-Agent Financial Intelligence Platform

> **PS-01 | HackVerse: Into the Web 2026**
>
> FinIntel is a multi-agent financial research and decision-support platform designed for retail investors. It combines market data, technical indicators, financial statements, regulatory filings, news sentiment, portfolio concentration analysis, and optional LLM-assisted synthesis into one explainable workflow.

**Important:** FinIntel is a research/demo system, **not financial advice**. Market data may be delayed, unavailable, or provider-dependent. The system is intentionally designed to surface uncertainty instead of inventing missing information.

---

## Overview

Retail investors often have to jump between price charts, financial statements, news, filings, and portfolio calculations before making sense of a stock.

FinIntel brings those signals together through a coordinated set of specialized agents:

```text
                         ┌─────────────────────────┐
                         │      User / React UI    │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │      FastAPI Backend     │
                         │        Orchestrator      │
                         └────────────┬────────────┘
                                      │
             ┌────────────────────────┼────────────────────────┐
             │                        │                        │
             ▼                        ▼                        ▼
      ┌─────────────┐         ┌─────────────┐          ┌─────────────┐
      │  Technical  │         │ Fundamental │          │  Sentiment  │
      │    Agent    │         │    Agent    │          │    Agent    │
      └──────┬──────┘         └──────┬──────┘          └──────┬──────┘
             │                       │                        │
             ▼                       ▼                        ▼
       Market / OHLCV        Financials + filings       News sources
       RSI / SMA / MACD       RAG / evidence             headline signals
             │                       │                        │
             └───────────────────────┼────────────────────────┘
                                     ▼
                           ┌────────────────────┐
                           │ Portfolio Risk     │
                           │ & Personalization  │
                           └─────────┬──────────┘
                                     ▼
                           ┌────────────────────┐
                           │ Confidence +       │
                           │ Conflict Detection │
                           └─────────┬──────────┘
                                     ▼
                           ┌────────────────────┐
                           │ Explainable        │
                           │ Recommendation     │
                           └────────────────────┘
```

The core idea is simple:

**Do not let one model make the entire decision.**

Instead, FinIntel separates evidence gathering from synthesis, keeps each agent's reasoning visible, records citations, and explicitly degrades when a data source is unavailable.

---

## Key Features

### 1. Multi-agent financial analysis

FinIntel uses specialized agents for different evidence dimensions:

| Agent | Purpose | Typical Evidence |
|---|---|---|
| Technical Agent | Price and momentum analysis | RSI, SMA20, SMA50, MACD, realized volatility, price/volume |
| Fundamental Agent | Financial quality and filings | Revenue, net income, EPS, margins, debt, cash flow, SEC filings |
| Sentiment Agent | Market/news sentiment | Recent headlines, positive/neutral/negative classification |
| Portfolio Risk Agent | Personal risk context | Position sizing, allocation, sector concentration, portfolio HHI |

Each agent emits a structured result rather than an unbounded natural-language answer.

---

### 2. Real market-data integration

The current implementation resolves Indian equities to Yahoo Finance symbols such as:

```text
RELIANCE → RELIANCE.NS
TCS      → TCS.NS
INFY     → INFY.NS
```

It also supports major Indian index aliases:

```text
NIFTY
NIFTY50
NIFTY 50
SENSEX
```

The market provider can retrieve:

- Current/most recent quote
- Previous close
- Change and change %
- Volume
- Market capitalization
- Day high / low
- 52-week high / low
- Sector / industry
- Historical OHLCV data
- Multiple historical ranges such as 1D, 1W, 1M, 3M, 6M, and 1Y

**Data note:** the code marks the Yahoo Finance feed as delayed and tracks data freshness. Availability can vary with provider/network conditions.

---

### 3. Technical indicators

The technical agent evaluates the available historical price series using indicators such as:

- RSI
- 20-day simple moving average
- 50-day simple moving average
- MACD
- Realized volatility
- Price vs. moving averages
- Momentum / trend structure

The agent converts these observations into a directional signal:

```text
BULLISH
BEARISH
NEUTRAL
UNAVAILABLE
```

It also produces a confidence estimate and a human-readable explanation.

---

### 4. Fundamental analysis and evidence retrieval

Fundamental analysis combines financial data and document evidence.

The financial provider can retrieve:

- Revenue
- Net income
- EPS
- Operating income
- Gross profit
- Total debt
- Cash
- Equity
- Operating cash flow
- Net margin
- Debt-to-equity
- Revenue growth
- Selected valuation / quality fields such as P/E and ROE when available

The filing provider integrates with **SEC EDGAR** for supported filings and records the source URLs as evidence.

The project also contains an in-process vector/RAG layer for evidence retrieval from stored financial documents and chunks.

The fundamental agent follows an important rule:

> **No retrieved evidence → no invented fundamental thesis.**

When retrieval fails, the agent returns an unavailable/abstain state instead of fabricating a filing or financial claim.

---

### 5. News sentiment

The sentiment pipeline can use a provider fallback chain:

1. **NewsAPI** when `NEWS_API_KEY` is configured
2. **Yahoo Finance News**
3. **Google News RSS**

The provider de-duplicates stories and extracts:

- Headline
- Publisher
- Article URL
- Publication time
- Company relevance
- Simple headline sentiment

The sentiment agent reports an aggregate view such as:

```text
POSITIVE
MIXED
NEGATIVE
UNAVAILABLE
```

The README should not be interpreted as claiming that headline sentiment is a forecast. The implementation explicitly treats it as a signal, not a prediction engine.

---

### 6. Portfolio-aware recommendations

FinIntel does not analyze a ticker in isolation.

The portfolio-risk layer considers:

- Existing holdings
- Quantity
- Current market value
- Position allocation
- Preferred maximum allocation
- Sector concentration
- Portfolio HHI concentration index
- User risk tolerance
- Investment horizon
- Investment objective
- Available capital
- Monthly contribution

This allows the same stock to produce different research conclusions depending on the investor's profile and existing exposure.

For example:

```text
Investor A
Conservative
High existing allocation
→ stronger concentration warning

Investor B
Aggressive
Low existing allocation
→ more room for a constructive signal
```

---

## Confidence System

FinIntel includes an explicit confidence-scoring layer rather than presenting a recommendation as certainty.

The confidence calculation considers:

- Base uncertainty
- Agent agreement
- Data completeness
- Evidence quality
- Data freshness
- Signal strength
- Conflicts between agents
- Missing/unavailable agents

The resulting score is a measure of **evidence quality and system confidence**.

It is **not**:

- a probability that a stock will rise
- a guarantee of performance
- a prediction accuracy score
- personalized financial advice

The UI exposes the underlying reasoning so users can see *why* confidence increased or decreased.

---

## Conflict Detection

Financial signals frequently disagree.

For example:

```text
Technical Agent     → BULLISH
Sentiment Agent     → BULLISH
Portfolio Risk      → BEARISH
Fundamental Agent   → NEUTRAL
```

FinIntel detects directional conflicts and reduces confidence when evidence is pulling in opposite directions.

The system is intentionally biased toward caution when there is disagreement:

```text
Strong disagreement
        ↓
Lower confidence
        ↓
More cautious recommendation
        ↓
User sees the conflict instead of a fake consensus
```

This is one of the core explainability principles of the project.

---

## Degraded Data Handling

A major design goal is **graceful degradation**.

The pipeline should not crash or silently convert missing data into confident claims.

Examples:

### Market feed unavailable

```text
Technical Agent
→ UNAVAILABLE

Recommendation
→ continues with remaining evidence
→ degraded flag displayed
→ confidence reduced
```

### Filing unavailable

```text
Fundamental Agent
→ UNAVAILABLE / INSUFFICIENT EVIDENCE

Recommendation
→ can still use market/news/portfolio evidence
→ does not invent a filing
```

### News unavailable

```text
Sentiment Agent
→ UNAVAILABLE

Recommendation
→ continues with other agents
```

### Everything unavailable

```text
No reliable evidence
→ WATCH / INSUFFICIENT EVIDENCE
```

This behavior is especially important for financial applications because missing information should reduce certainty rather than increase it.

---

## Personalization

The backend stores investor profiles and uses them during synthesis.

The system supports profile attributes such as:

- Risk tolerance
- Investment horizon
- Capital
- Monthly investment amount
- Maximum preferred single-stock allocation
- Objective
- Existing holdings

The synthesis stage can therefore produce different conclusions for the same stock without changing the underlying market input.

---

## Optional LLM Layer

An LLM is available as an **optional reasoning / rewriting layer**.

The control plane does not depend on an LLM being available.

When configured, the LLM is used for tasks such as:

- Producing cautious natural-language narratives
- Answering grounded follow-up questions
- Improving presentation of structured analysis

The model prompt explicitly constrains the assistant to use only supplied evidence and to respond with insufficient-evidence language when facts are missing.

### Why this matters

The deterministic pipeline remains the source of truth for:

- data collection
- indicator calculations
- agent signals
- evidence retrieval
- confidence
- conflict detection
- portfolio calculations
- safety rules

That makes the system easier to replay, debug, and audit.

---

# Technology Stack

## Backend

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic
- SQLite
- NumPy
- Pandas
- yfinance
- HTTP clients for external data
- In-process RAG/vector store
- Optional OpenAI-compatible LLM endpoint

## Frontend

- React 19
- Vite 7
- Modern CSS
- Dark financial-terminal style interface

## Data / external sources

- Yahoo Finance
- NewsAPI (optional)
- Google News RSS
- SEC EDGAR
- Optional OpenAI-compatible API

---

# Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── pipeline.py
│   │   │   └── graph.py
│   │   │
│   │   ├── market/
│   │   ├── rag/
│   │   │   ├── corpus.py
│   │   │   └── store.py
│   │   │
│   │   ├── services/
│   │   │   ├── confidence.py
│   │   │   ├── indicators.py
│   │   │   ├── llm.py
│   │   │   ├── planner.py
│   │   │   ├── portfolio.py
│   │   │   └── data_providers/
│   │   │       ├── filing_provider.py
│   │   │       ├── financial_provider.py
│   │   │       ├── market_provider.py
│   │   │       └── news_provider.py
│   │   │
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── schemas.py
│   │   └── ...
│   │
│   └── tests/
│       └── test_pipeline.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.js
│
├── data/
│   ├── finint.db
│   └── chroma/
│
├── .env.example
├── requirements.txt
├── ARCHITECTURE.md
├── pytest.ini
└── README.md
```

> Generated/cache directories such as `node_modules`, `__pycache__`, build output, and local database artifacts should generally not be committed to GitHub unless intentionally required.

---

# Local Setup

## Prerequisites

Recommended:

- Python 3.12+
- Node.js 18+ or newer
- npm
- Git

Optional:

- NewsAPI key
- OpenAI-compatible API key
- Market/fundamental provider credentials
- SEC-related credentials where applicable

---

## 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_FOLDER>
```

---

## 2. Create a Python virtual environment

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

The runtime imports additional packages used by the current provider implementation (for example Pandas, yfinance, and python-dotenv). If your environment reports one of these as missing, install the corresponding package or update the dependency manifest before deployment.

---

## 4. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Example:

```env
MARKET_API_KEY=
NEWS_API_KEY=
LLM_API_KEY=
SEC_API_KEY=

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

FININT_HOST=127.0.0.1
FININT_PORT=8000
DATABASE_PATH=data/finint.db
CHROMA_PATH=data/chroma
HTTP_TIMEOUT_SECONDS=20
```

### Important

Never commit real API keys to GitHub.

Use:

```text
.env
```

locally and keep secrets out of source control.

---

# Frontend Setup

From the repository root:

```bash
npm --prefix frontend install
```

To start the Vite development server:

```bash
npm --prefix frontend run dev
```

The development frontend normally runs on:

```text
http://127.0.0.1:5173
```

The API runs separately on port 8000.

---

# Run the Backend

From the repository root:

### Windows PowerShell

```powershell
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

### macOS / Linux

```bash
PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

API:

```text
http://127.0.0.1:8000
```

---

# Production-style Local Run

Build the React frontend:

```bash
npm --prefix frontend run build
```

Then launch FastAPI:

### Windows PowerShell

```powershell
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### macOS / Linux

```bash
PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

FastAPI serves the generated React application from:

```text
frontend/dist
```

Open:

```text
http://127.0.0.1:8000
```

---

# API Reference

## Health

```http
GET /api/health
```

Returns basic health information and the supported universe.

Example:

```json
{
  "ok": true,
  "universe": [...]
}
```

---

## Market data

```http
GET /api/market
```

Returns the current market universe.

The implementation also supports the optional feed-down simulation/query behavior used by the project.

---

## User profiles

```http
GET /api/users
```

Returns investor profiles available to the UI.

---

## Scenarios

```http
GET /api/scenarios
```

Returns supported analysis scenarios.

These scenarios are useful for demos and failure-mode testing.

---

## Run analysis

```http
POST /api/analyze
Content-Type: application/json
```

Request:

```json
{
  "symbol": "RELIANCE",
  "user_id": "priya",
  "scenario": "base"
}
```

The analysis response contains the structured outputs used by the frontend, including:

- market/quote information
- agent results
- evidence
- recommendation / synthesis
- confidence information
- reasoning chain
- portfolio information
- metrics
- degraded-data state where applicable

---

## Session history

```http
GET /api/sessions
```

Returns recent stored analysis sessions.

---

# Example Analysis Flow

A typical request looks like this:

```text
POST /api/analyze
        │
        ▼
Resolve symbol
        │
        ▼
Fetch quote + historical market data
        │
        ├───────────────┐
        ▼               ▼
Technical Agent    Fundamental Agent
        │               │
        │               ├─ Financial statements
        │               └─ Filing / RAG evidence
        │
        └───────────────┐
                        ▼
                  Sentiment Agent
                        │
                        ├─ NewsAPI (optional)
                        ├─ Yahoo Finance News
                        └─ Google News RSS

                        +
                  Portfolio Risk
                        │
                        ▼
               Conflict Detection
                        │
                        ▼
             Confidence Calculation
                        │
                        ▼
                Final Synthesis
                        │
                        ▼
             Explainable UI + Session Log
```

---

# Demo Scenarios

The project contains scenarios intended to demonstrate both normal operation and failure handling.

### Base

Normal multi-agent analysis.

```text
scenario = "base"
```

### Feed Down

Simulates degraded market data.

```text
scenario = "feed_down"
```

Expected behavior:

- technical analysis becomes unavailable
- pipeline does not crash
- recommendation is produced only from remaining usable evidence
- degraded state is surfaced

### Missing Filing

Simulates missing fundamental-document evidence.

```text
scenario = "missing_filing"
```

Expected behavior:

- fundamental agent abstains
- no filing claim is fabricated
- other agents can still contribute

### Conflict

Simulates a disagreement between directional signals.

```text
scenario = "conflict"
```

Expected behavior:

- disagreement is visible
- confidence is reduced
- synthesis becomes more cautious

---

# Testing

Run the test suite with:

### Windows PowerShell

```powershell
$env:PYTHONPATH="backend"
pytest backend/tests -q
```

### macOS / Linux

```bash
PYTHONPATH=backend pytest backend/tests -q
```

The current tests cover important system guarantees, including:

- all required agents being present
- three-dimensional signal generation
- investor-profile personalization
- missing-filing behavior
- feed-down resilience
- conflict detection
- session metrics logging

---

# Safety and Reliability Principles

FinIntel is designed around several explicit rules.

### No evidence, no confident claim

Missing data should produce uncertainty.

### No invented citations

An agent must not create a filing, quote, article, or source that it did not retrieve.

### Agent failures are isolated

One unavailable provider or agent should not automatically destroy the entire analysis.

### Conflicts reduce confidence

The system does not force all agents into consensus.

### Personalization is explicit

The recommendation is a function of both market evidence and portfolio/risk context.

### LLMs are optional

Core calculations and safety logic remain deterministic and inspectable.

---

# Why This Architecture?

A conventional stock chatbot looks like:

```text
User → LLM → Answer
```

FinIntel is closer to:

```text
Data
  ↓
Specialized agents
  ↓
Evidence + structured signals
  ↓
Risk / portfolio context
  ↓
Conflict detection
  ↓
Confidence
  ↓
Synthesis
  ↓
Explainable recommendation
```

This separation gives the system a few practical advantages:

- easier debugging
- clearer attribution
- better handling of provider failures
- reproducible calculations
- visible reasoning
- easier auditing
- easier future replacement of individual agents

It also makes it possible to improve one component without replacing the entire system.

---

# Future Enhancements

Potential next steps include:

- Streaming WebSocket market updates
- Better NSE/BSE-specific providers
- Dedicated options/F&O analytics
- More sophisticated financial statement normalization
- Full vector database integration
- SEC/NSE/BSE document ingestion pipelines
- Earnings-call transcript ingestion
- Time-series forecasting agents
- Sector and macro agents
- Backtesting and historical evaluation dashboards
- Agent-level benchmark datasets
- More advanced semantic sentiment models
- Authentication and multi-user accounts
- Cloud deployment
- Background task orchestration with Celery or Temporal
- Observability dashboards for API/provider latency
- Model routing across multiple LLM providers

---

# Known Limitations

FinIntel is a hackathon/demo-oriented research platform.

Current limitations include:

1. External providers can be delayed, rate-limited, or temporarily unavailable.
2. News sentiment is based on headline-level heuristics rather than a full NLP research stack.
3. Financial-data availability varies by ticker and provider.
4. SEC EDGAR coverage is not equivalent to universal coverage of every Indian regulatory disclosure.
5. Confidence is an evidence-quality score, not a predictive probability.
6. Portfolio decisions depend on the quality and freshness of stored holdings.
7. Some LLM-assisted text is optional and should never be treated as independently verified market truth.
8. Production deployment would require stronger authentication, secrets management, rate limiting, monitoring, and compliance controls.

---

# Security Notes

Before publishing the repository:

```text
DO NOT COMMIT
├── .env
├── API keys
├── access tokens
├── private credentials
├── local secrets
└── unnecessary runtime databases
```

Use `.env.example` as the safe template.

Recommended GitHub hygiene:

```bash
git status
git diff
git ls-files | findstr ".env"
```

Make sure no credentials appear in the repository history.

---

# Disclaimer

**FinIntel is an educational and research-oriented software project.**

It does not provide individualized financial advice, investment guarantees, or certainty about future returns.

Any action labels or portfolio suggestions shown by the application should be interpreted as machine-generated research signals based on available data and system rules.

Always independently verify important financial information and consult a qualified financial professional where appropriate.

---

# Project Information

**Project:** FinIntel  
**Problem Statement:** PS-01 — Multi-Agent Autonomous Financial Intelligence System for Retail Investors  
**Event:** HackVerse: Into the Web  
**Built for:** Rapid hackathon demonstration and explainable financial intelligence research

---

## Quick Start

For the fastest local run:

```bash
# Backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt

# Frontend
npm --prefix frontend install
npm --prefix frontend run build

# Backend
# Windows PowerShell:
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Open
http://127.0.0.1:8000
```

---

## Credits

Built as a multi-agent financial intelligence prototype with a focus on:

**Real data → specialized agents → grounded evidence → portfolio context → confidence → explainable synthesis.**

