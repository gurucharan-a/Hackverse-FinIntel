# FinIntel — Multi-agent autonomous financial intelligence

PS-01 demo: convert a market tape, SEBI-style filings, and a retail risk profile into a **cited, personalized** cash-equity recommendation in one pass, with the full reasoning chain visible.

This is **not** investment advice. The tape is a seeded NSE-like simulator; filings are synthetic documents written in the style of public disclosures.

## Why this architecture

Retail tools usually stop at a screener or a headline. Hedge desks run parallel specialists (technicals, fundamentals, flows) and then a PM synthesizes. FinIntel copies that **org chart**, not a single chatbot:

1. Ingest tape → classify three independent signal dimensions (momentum, volume anomaly, sentiment).
2. Dispatch **three agents in parallel** with a shared output contract (`stance`, `confidence`, `thesis`, `citations`, `degraded`).
3. Ground the fundamental agent with **TF-IDF cosine retrieval** over a filing/transcript corpus (attribution is user-visible).
4. Synthesize with **profile-dependent weights** and hard safety rails (F&O block, concentration cap, FOMO fade, no uncited claims).
5. Log session metrics: agent latency, 30-day forward-return alignment proxy, portfolio HHI.

Deterministic agents are intentional. Judges can replay the same inputs and audit every weight. An LLM can later rewrite theses; it is not required for the control plane.

## Agents

| Agent | Role | Inputs | Failure mode |
| --- | --- | --- | --- |
| `technical` | Momentum / volume structure | Last, RSI-14, 20d momentum, volume vs 20d avg | Feed down → `abstain` |
| `fundamental` | Filings & earnings RAG | Vector search over transcripts / SEBI-style docs | Retrieval miss → `abstain`, no invented filing |
| `sentiment` | FII + options crowding | FII ₹ Cr, put-call ratio, macro FII note | Feed down → macro-only, marked degraded |

Synthesis weights:

- Conservative: fundamentals 0.55, sentiment 0.27, technicals 0.18
- Balanced: fundamentals 0.42, sentiment 0.30, technicals 0.28
- Aggressive: technicals 0.40, sentiment 0.32, fundamentals 0.28

Conflicts (bullish **and** bearish among live agents) cap confidence and prefer `watch`/`hold` over a one-sided add.

## Demo script (under 60 seconds)

1. Start the stack. Default load: **Priya (conservative)** × **RELIANCE** (constructive tape + clean filings + FII bid) → typically **hold/add** with citations to Q1 transcript and shareholding pattern.
2. Switch investor to **Arjun (aggressive)** without changing the symbol → personalization notes and often the action change (size / FOMO rails).
3. Run scenario **Conflict: Zomato** → hot RSI/volume vs margin compression + promoter-sale filing. Trace shows disagreement; synthesis will not pretend consensus.
4. Run **missing filing** on PAYTM or any name → fundamental agent abstains; UI still shows a cited rec from tape/macro.
5. Run **feed down** on HDFCBANK → technical abstains; pipeline does not crash.

Profiles stored in `backend/app/profiles.py`:

- Priya Sharma — conservative, no F&O, loss-averse, bank-heavy book
- Arjun Mehta — aggressive, F&O flag on (system still refuses to size derivatives), FOMO history, Zomato/Paytm book
- Meera Iyer — balanced, mixed book

## Metrics (per session)

Written to `data/sessions.jsonl`:

- `agent_response_latency_ms` — wall time of the slowest parallel agent
- `signal_accuracy_proxy` — 1 if composite signal sign matches seeded 30-day forward return, else 0 (`null` if feed degraded)
- `portfolio_risk_concentration` — Herfindahl-Hirschman index of holdings

## Degraded-data contract

The pipeline **must not** fail closed into an uncited recommendation. Rules:

- No citations → agent stance is `abstain`.
- Synthesis may continue using remaining agents but **caps confidence** and sets safety flags.
- Composite output always carries at least one citation from a live agent or the macro corpus, or it is a pure `watch` with an explicit data-gap thesis.

## Stack

- Python 3.12+ / FastAPI orchestrator (`backend/app`)
- In-process vector index (`backend/app/rag`)
- React + Vite desk (`frontend`)
- ThreadPoolExecutor for parallel agents (swap-ready for Celery / Temporal)

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
npm --prefix frontend install
npm --prefix frontend run build
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000

Dev UI (API on :8000, Vite on :5173):

```bash
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
npm --prefix frontend run dev
```

Tests:

```bash
$env:PYTHONPATH="backend"
pytest backend/tests -q
```
