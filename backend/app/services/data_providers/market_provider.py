from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from app.config import MARKET_KEY_SET
from app.db import db, utcnow
from app.schemas import Bar, DataMeta, History, Quote
from app.services.http import timed_call, timed_get
from app.services.indicators import sma
from app.services.timeutil import classify_freshness, iso_ist
from app.services.textutil import uid

INDEX_MAP = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTY 50": "^NSEI",
    "^NSEI": "^NSEI",
    "SENSEX": "^BSESN",
    "^BSESN": "^BSESN",
}

RANGE_MAP = {
    "1D": ("1d", "5m"),
    "1W": ("7d", "15m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
}

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"


def resolve_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not s:
        return s
    if s in INDEX_MAP:
        return INDEX_MAP[s]
    if s.startswith("^") or "." in s:
        return s
    return f"{s}.NS"


def display_symbol(yahoo: str) -> str:
    if yahoo.startswith("^"):
        return {"^NSEI": "NIFTY 50", "^BSESN": "SENSEX"}.get(yahoo, yahoo)
    return yahoo.replace(".NS", "").replace(".BO", "")


def _meta(ts: datetime | None, available: bool) -> DataMeta:
    freshness = classify_freshness(ts, delayed_feed=True) if available else "UNAVAILABLE"
    return DataMeta(
        source="Yahoo Finance",
        provider="yahoo_finance",
        timestamp=iso_ist(ts) if ts else None,
        freshness=freshness if available else "UNAVAILABLE",
    )


class MarketProvider:
    name = "Yahoo Finance"
    delayed = True

    def configured(self) -> bool:
        return True

    def search(self, query: str) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        resp, _, err = timed_get(
            "yahoo_finance",
            SEARCH_URL,
            params={"q": q, "quotesCount": 8, "newsCount": 0, "lang": "en-IN"},
        )
        out: list[dict[str, Any]] = []
        if resp is not None:
            for item in resp.json().get("quotes", [])[:8]:
                symbol = item.get("symbol")
                if not symbol:
                    continue
                out.append(
                    {
                        "symbol": display_symbol(symbol),
                        "yahoo_symbol": symbol,
                        "name": item.get("shortname") or item.get("longname") or symbol,
                        "exchange": item.get("exchDisp") or item.get("exchange"),
                        "type": item.get("quoteType"),
                    }
                )
        if not out:
            ysym = resolve_symbol(q)
            quote = self.quote(ysym)
            if quote.available:
                out.append(
                    {
                        "symbol": quote.symbol,
                        "yahoo_symbol": quote.yahoo_symbol,
                        "name": quote.name,
                        "exchange": quote.exchange,
                        "type": "EQUITY",
                    }
                )
        return out

    def quote(self, yahoo_symbol: str) -> Quote:
        ysym = resolve_symbol(yahoo_symbol)

        def _fetch():
            t = yf.Ticker(ysym)
            info = {}
            try:
                info = t.get_fast_info()  # type: ignore[attr-defined]
                info = dict(info) if not isinstance(info, dict) else info
            except Exception:
                info = {}
            # fast_info may be object
            def g(key, default=None):
                if isinstance(info, dict):
                    return info.get(key, default)
                return getattr(info, key, default)

            last = g("last_price") or g("lastPrice")
            prev = g("previous_close") or g("previousClose")
            currency = g("currency") or "INR"
            exch = g("exchange")
            extra = {}
            try:
                extra = t.info or {}
            except Exception:
                extra = {}
            return last, prev, currency, exch, extra, g("last_volume") or g("threeMonthAverageVolume")

        result, _, err = timed_call("yahoo_finance", f"quote:{ysym}", _fetch)
        if not result or result[0] is None:
            return Quote(
                symbol=display_symbol(ysym),
                yahoo_symbol=ysym,
                available=False,
                meta=_meta(None, False),
            )
        last, prev, currency, exch, extra, volume = result
        last_f = float(last)
        prev_f = float(prev) if prev is not None else None
        change = (last_f - prev_f) if prev_f is not None else None
        change_pct = (change / prev_f * 100) if change is not None and prev_f else None
        ts = datetime.now(timezone.utc)
        q = Quote(
            symbol=display_symbol(ysym),
            yahoo_symbol=ysym,
            name=extra.get("shortName") or extra.get("longName"),
            exchange=extra.get("exchange") or exch,
            currency=extra.get("currency") or currency or "INR",
            price=last_f,
            previous_close=prev_f,
            change=round(change, 4) if change is not None else None,
            change_pct=round(change_pct, 4) if change_pct is not None else None,
            volume=float(volume) if volume is not None else extra.get("volume"),
            market_cap=extra.get("marketCap"),
            day_high=extra.get("dayHigh"),
            day_low=extra.get("dayLow"),
            fifty_two_week_high=extra.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=extra.get("fiftyTwoWeekLow"),
            sector=extra.get("sector"),
            industry=extra.get("industry"),
            available=True,
            meta=_meta(ts, True),
        )
        with db() as conn:
            conn.execute(
                """INSERT INTO market_data (yahoo_symbol, payload, fetched_at, source)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(yahoo_symbol) DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at""",
                (ysym, q.model_dump_json(), utcnow(), "yahoo_finance"),
            )
        return q

    def history(self, yahoo_symbol: str, range_key: str = "1M") -> History:
        ysym = resolve_symbol(yahoo_symbol)
        period, interval = RANGE_MAP.get(range_key.upper(), RANGE_MAP["1M"])

        def _fetch():
            t = yf.Ticker(ysym)
            return t.history(period=period, interval=interval, auto_adjust=False)

        df, _, err = timed_call("yahoo_finance", f"history:{ysym}:{range_key}", _fetch)
        empty_meta = _meta(None, False)
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return History(
                yahoo_symbol=ysym,
                range=range_key,
                interval=interval,
                available=False,
                meta=empty_meta,
            )
        bars: list[Bar] = []
        closes: list[float] = []
        for idx, row in df.iterrows():
            if pd.isna(row.get("Close")):
                continue
            ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else datetime.now(timezone.utc)
            close = float(row["Close"])
            bars.append(
                Bar(
                    time=iso_ist(ts),
                    open=float(row.get("Open", close) or close),
                    high=float(row.get("High", close) or close),
                    low=float(row.get("Low", close) or close),
                    close=close,
                    volume=float(row.get("Volume", 0) or 0),
                )
            )
            closes.append(close)
        last_ts = None
        if bars:
            try:
                last_ts = datetime.fromisoformat(bars[-1].time)
            except Exception:
                last_ts = datetime.now(timezone.utc)
        return History(
            yahoo_symbol=ysym,
            range=range_key,
            interval=interval,
            bars=bars,
            sma20=sma(closes, 20) if range_key != "1D" else [],
            sma50=sma(closes, 50) if range_key not in {"1D", "1W"} else [],
            available=bool(bars),
            meta=_meta(last_ts, bool(bars)),
        )

    def overview(self) -> dict[str, Any]:
        nifty = self.quote("^NSEI")
        sensex = self.quote("^BSESN")
        hist = self.history("^NSEI", "3M")
        from app.services.indicators import rsi

        closes = [b.close for b in hist.bars]
        nifty_rsi = rsi(closes) if closes else None
        sentiment = "UNAVAILABLE"
        if nifty.available and nifty.change_pct is not None:
            ch = nifty.change_pct
            if ch >= 0.6 or (nifty_rsi is not None and nifty_rsi >= 60 and ch > 0):
                sentiment = "BULLISH"
            elif ch <= -0.6 or (nifty_rsi is not None and nifty_rsi <= 40 and ch < 0):
                sentiment = "BEARISH"
            else:
                sentiment = "NEUTRAL"
        completeness = sum(
            [
                1 if nifty.available else 0,
                1 if sensex.available else 0,
                1 if hist.available else 0,
                1 if nifty_rsi is not None else 0,
            ]
        )
        confidence = round(40 + completeness * 12, 1) if completeness else None
        if confidence is not None and sentiment == "UNAVAILABLE":
            confidence = None
        return {
            "nifty": nifty.model_dump(),
            "sensex": sensex.model_dump(),
            "sentiment": sentiment,
            "sentiment_inputs": {
                "nifty_change_pct": nifty.change_pct,
                "nifty_rsi": nifty_rsi,
            },
            "ai_market_confidence": confidence,
            "confidence_note": "Derived from index data completeness and NIFTY trend/RSI. Not a forecast.",
            "keys_configured": {"market_api_key": MARKET_KEY_SET},
        }


market_provider = MarketProvider()
