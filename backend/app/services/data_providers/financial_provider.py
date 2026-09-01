from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from app.db import db, utcnow
from app.schemas import DataMeta, EvidenceItem
from app.services.data_providers.market_provider import display_symbol, resolve_symbol
from app.services.http import timed_call
from app.services.textutil import uid
from app.services.timeutil import iso_ist

PERIOD_LABELS = ["ttm", "annual", "quarterly"]


def _fmt_num(v: Any) -> str:
    try:
        n = float(v)
    except Exception:
        return str(v)
    if abs(n) >= 1e7:
        return f"{n/1e7:.2f} Cr"
    if abs(n) >= 1e5:
        return f"{n/1e5:.2f} L"
    return f"{n:,.2f}"


def _latest_col(df: pd.DataFrame) -> Any:
    if df is None or df.empty:
        return None
    return df.columns[0]


class FinancialProvider:
    def snapshot(self, yahoo_symbol: str) -> dict[str, Any]:
        ysym = resolve_symbol(yahoo_symbol)

        def _fetch():
            t = yf.Ticker(ysym)
            financials = t.financials
            balance = t.balance_sheet
            cash = t.cashflow
            info = {}
            try:
                info = t.info or {}
            except Exception:
                info = {}
            return financials, balance, cash, info

        result, _, err = timed_call("yahoo_finance", f"financials:{ysym}", _fetch)
        if not result:
            return {
                "available": False,
                "error": err or "DATA UNAVAILABLE",
                "metrics": {},
                "evidence": [],
                "source": "Yahoo Finance",
            }
        financials, balance, cash, info = result
        metrics: dict[str, Any] = {}
        evidence: list[EvidenceItem] = []
        snippets: list[str] = []

        def pick(df: pd.DataFrame, keys: list[str], dest: str, statement: str) -> None:
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                return
            col = _latest_col(df)
            for key in keys:
                if key in df.index:
                    val = df.loc[key, col]
                    if pd.isna(val):
                        continue
                    metrics[dest] = float(val)
                    period = str(col)[:10]
                    text = f"{statement}: {key} for period {period} is {_fmt_num(val)}."
                    snippets.append(text)
                    evidence.append(
                        EvidenceItem(
                            id=uid("fin", ysym, dest, period),
                            source="Yahoo Finance",
                            title=f"{statement} — {key}",
                            company=display_symbol(ysym),
                            category="FINANCIALS",
                            url=f"https://finance.yahoo.com/quote/{ysym}/financials",
                            snippet=text,
                            agent="fundamental",
                            relevance=0.9,
                            published_at=period,
                            timestamp=iso_ist(datetime.now(timezone.utc)),
                        )
                    )
                    return

        pick(financials, ["Total Revenue", "Operating Revenue"], "revenue", "Income statement")
        pick(financials, ["Net Income", "Net Income Common Stockholders"], "net_income", "Income statement")
        pick(financials, ["Diluted EPS", "Basic EPS"], "eps", "Income statement")
        pick(financials, ["Operating Income"], "operating_income", "Income statement")
        pick(financials, ["Gross Profit"], "gross_profit", "Income statement")
        pick(balance, ["Total Debt", "Net Debt"], "total_debt", "Balance sheet")
        pick(balance, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"], "cash", "Balance sheet")
        pick(balance, ["Stockholders Equity", "Common Stock Equity"], "equity", "Balance sheet")
        pick(cash, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], "operating_cash_flow", "Cash flow")

        if metrics.get("revenue") and metrics.get("net_income") is not None:
            metrics["net_margin"] = round(metrics["net_income"] / metrics["revenue"] * 100, 2)
        if metrics.get("equity") and metrics.get("total_debt") is not None:
            metrics["debt_to_equity"] = round(metrics["total_debt"] / metrics["equity"], 3) if metrics["equity"] else None

        # growth if two columns exist
        if isinstance(financials, pd.DataFrame) and not financials.empty and "Total Revenue" in financials.index:
            row = financials.loc["Total Revenue"].dropna()
            if len(row) >= 2:
                newer, older = float(row.iloc[0]), float(row.iloc[1])
                if older:
                    metrics["revenue_growth"] = round((newer / older - 1) * 100, 2)
                    snippets.append(
                        f"Revenue changed {metrics['revenue_growth']}% between {str(row.index[1])[:10]} and {str(row.index[0])[:10]}."
                    )

        for k in ("trailingPE", "forwardPE", "profitMargins", "returnOnEquity", "currentRatio"):
            if info.get(k) is not None:
                metrics[k] = info[k]

        available = bool(metrics)
        doc_id = uid("doc", ysym, "financials")
        if snippets:
            with db() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO documents (id, yahoo_symbol, title, source, url, doc_type, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        doc_id,
                        ysym,
                        f"{display_symbol(ysym)} financial statements",
                        "Yahoo Finance",
                        f"https://finance.yahoo.com/quote/{ysym}/financials",
                        "FINANCIALS",
                        utcnow(),
                    ),
                )
                for i, sn in enumerate(snippets):
                    conn.execute(
                        """INSERT OR REPLACE INTO document_chunks (id, document_id, chunk_index, text, page)
                           VALUES (?, ?, ?, ?, ?)""",
                        (uid("chunk", doc_id, str(i)), doc_id, i, sn, None),
                    )
        return {
            "available": available,
            "metrics": metrics,
            "evidence": [e.model_dump() for e in evidence],
            "snippets": snippets,
            "source": "Yahoo Finance",
            "url": f"https://finance.yahoo.com/quote/{ysym}/financials",
            "error": None if available else "DATA UNAVAILABLE",
            "info_subset": {
                "longBusinessSummary": (info.get("longBusinessSummary") or "")[:1200] or None,
                "fullTimeEmployees": info.get("fullTimeEmployees"),
            },
        }


financial_provider = FinancialProvider()
