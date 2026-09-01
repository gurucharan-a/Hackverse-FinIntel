from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.config import SEC_KEY_SET, USER_AGENT
from app.db import db, utcnow
from app.schemas import EvidenceItem
from app.services.data_providers.market_provider import display_symbol, resolve_symbol
from app.services.http import timed_get
from app.services.textutil import uid
from app.services.timeutil import iso_ist

SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


class FilingProvider:
    def fetch(self, yahoo_symbol: str) -> dict[str, Any]:
        ysym = resolve_symbol(yahoo_symbol)
        # Indian listings are not on EDGAR.
        if ysym.endswith(".NS") or ysym.endswith(".BO") or ysym.startswith("^"):
            return {
                "available": False,
                "filings": [],
                "evidence": [],
                "source": "SEC EDGAR",
                "error": "FINANCIAL DOCUMENT UNAVAILABLE — SEC EDGAR does not cover this listing. Fundamentals use Yahoo Finance statements instead.",
            }
        ticker = ysym.split(".")[0].upper()
        headers = {"User-Agent": USER_AGENT}
        if SEC_KEY_SET:
            headers["Authorization"] = f"Bearer {os.getenv('SEC_API_KEY')}"
        resp, _, err = timed_get("sec_edgar", SEC_TICKERS, headers=headers)
        if resp is None:
            return {
                "available": False,
                "filings": [],
                "evidence": [],
                "source": "SEC EDGAR",
                "error": err or "DATA UNAVAILABLE",
            }
        cik = None
        try:
            mapping = resp.json()
            for row in mapping.values() if isinstance(mapping, dict) else []:
                if str(row.get("ticker", "")).upper() == ticker:
                    cik = str(row.get("cik_str")).zfill(10)
                    break
        except Exception as exc:
            return {"available": False, "filings": [], "evidence": [], "source": "SEC EDGAR", "error": str(exc)[:200]}
        if not cik:
            return {
                "available": False,
                "filings": [],
                "evidence": [],
                "source": "SEC EDGAR",
                "error": "FINANCIAL DOCUMENT UNAVAILABLE — CIK not found for ticker.",
            }
        sub, _, err = timed_get("sec_edgar", SEC_SUBMISSIONS.format(cik=cik), headers=headers)
        if sub is None:
            return {"available": False, "filings": [], "evidence": [], "source": "SEC EDGAR", "error": err or "DATA UNAVAILABLE"}
        data = sub.json()
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        dates = recent.get("filingDate", [])
        filings = []
        evidence: list[EvidenceItem] = []
        for i, form in enumerate(forms[:8]):
            if form not in {"10-K", "10-Q", "8-K", "20-F", "6-K"}:
                continue
            acc = accessions[i].replace("-", "")
            doc = docs[i]
            date = dates[i] if i < len(dates) else None
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
            filings.append({"form": form, "date": date, "url": url, "accession": accessions[i]})
            evidence.append(
                EvidenceItem(
                    id=uid("sec", accessions[i]),
                    source="SEC EDGAR",
                    title=f"{form} filed {date}",
                    company=display_symbol(ysym),
                    category="FILINGS",
                    url=url,
                    snippet=f"{form} primary document {doc} dated {date}.",
                    agent="fundamental",
                    relevance=0.85 if form in {"10-K", "10-Q"} else 0.7,
                    published_at=date,
                    timestamp=iso_ist(datetime.now(timezone.utc)),
                )
            )
            with db() as conn:
                did = uid("secdoc", accessions[i])
                conn.execute(
                    """INSERT OR REPLACE INTO documents (id, yahoo_symbol, title, source, url, doc_type, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (did, ysym, f"{form} {date}", "SEC EDGAR", url, "FILINGS", utcnow()),
                )
        return {
            "available": bool(filings),
            "filings": filings,
            "evidence": [e.model_dump() for e in evidence],
            "source": "SEC EDGAR",
            "error": None if filings else "FINANCIAL DOCUMENT UNAVAILABLE",
        }


filing_provider = FilingProvider()
