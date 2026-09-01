from __future__ import annotations

import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import yfinance as yf

from app.config import NEWS_KEY_SET
from app.db import db, utcnow
from app.schemas import DataMeta, NewsItem
from app.services.data_providers.market_provider import display_symbol, resolve_symbol
from app.services.http import timed_call, timed_get
from app.services.textutil import headline_sentiment, relevance_to_symbol, uid
from app.services.timeutil import classify_freshness, iso_ist

NEWSAPI_URL = "https://newsapi.org/v2/everything"
GOOGLE_RSS = "https://news.google.com/rss/search"


def _meta(ts: datetime | None, source: str, available: bool) -> DataMeta:
    return DataMeta(
        source=source,
        provider="newsapi" if source == "NewsAPI" else "yahoo_finance" if "Yahoo" in source else "google_news",
        timestamp=iso_ist(ts) if ts else None,
        freshness=classify_freshness(ts, delayed_feed=True) if available else "UNAVAILABLE",
    )


class NewsProvider:
    def configured(self) -> bool:
        return True

    def fetch(self, yahoo_symbol: str, name: str | None = None, limit: int = 12) -> list[NewsItem]:
        ysym = resolve_symbol(yahoo_symbol)
        items: list[NewsItem] = []
        if NEWS_KEY_SET:
            items.extend(self._newsapi(ysym, name, limit))
        if len(items) < 3:
            items.extend(self._yahoo(ysym, name, limit))
        if len(items) < 3:
            items.extend(self._google_rss(ysym, name, limit))
        # de-dupe by url/title
        seen: set[str] = set()
        unique: list[NewsItem] = []
        for it in items:
            key = (it.url or it.title).lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(it)
        for it in unique[:limit]:
            with db() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO news
                       (id, yahoo_symbol, title, publisher, url, published_at, sentiment, payload, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        it.id,
                        ysym,
                        it.title,
                        it.publisher,
                        it.url,
                        it.published_at,
                        it.sentiment,
                        it.model_dump_json(),
                        utcnow(),
                    ),
                )
        return unique[:limit]

    def _newsapi(self, ysym: str, name: str | None, limit: int) -> list[NewsItem]:
        key = (os.getenv("NEWS_API_KEY") or "").strip()
        q = name or display_symbol(ysym)
        resp, _, _ = timed_get(
            "newsapi",
            NEWSAPI_URL,
            params={"q": q, "language": "en", "sortBy": "publishedAt", "pageSize": limit, "apiKey": key},
        )
        if resp is None:
            return []
        out = []
        for a in resp.json().get("articles", []):
            title = a.get("title") or ""
            if not title or title == "[Removed]":
                continue
            pub = None
            if a.get("publishedAt"):
                try:
                    pub = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                except Exception:
                    pub = None
            sent, _ = headline_sentiment(title)
            out.append(
                NewsItem(
                    id=uid("newsapi", a.get("url") or title),
                    title=title,
                    publisher=(a.get("source") or {}).get("name"),
                    url=a.get("url"),
                    published_at=iso_ist(pub) if pub else None,
                    sentiment=sent,
                    relevance=relevance_to_symbol(title, name, ysym),
                    yahoo_symbol=ysym,
                    meta=_meta(pub or datetime.now(timezone.utc), "NewsAPI", True),
                )
            )
        return out

    def _yahoo(self, ysym: str, name: str | None, limit: int) -> list[NewsItem]:
        def _fetch():
            return yf.Ticker(ysym).news or []

        raw, _, _ = timed_call("yahoo_finance", f"news:{ysym}", _fetch)
        if not raw:
            return []
        out: list[NewsItem] = []
        for n in raw[:limit]:
            content = n.get("content") if isinstance(n.get("content"), dict) else {}
            title = n.get("title") or content.get("title") or ""
            if not title:
                continue
            url = None
            click = content.get("clickThroughUrl") or {}
            if isinstance(click, dict):
                url = click.get("url")
            url = url or n.get("link") or n.get("url")
            publisher = None
            provider = content.get("provider") or {}
            if isinstance(provider, dict):
                publisher = provider.get("displayName")
            publisher = publisher or n.get("publisher")
            pub = None
            for key in ("pubDate", "providerPublishTime", "published_at"):
                val = content.get("pubDate") or n.get(key)
                if val is None:
                    continue
                try:
                    if isinstance(val, (int, float)):
                        pub = datetime.fromtimestamp(val if val > 1e12 else val, tz=timezone.utc) if val > 1e10 else datetime.fromtimestamp(val, tz=timezone.utc)
                    else:
                        pub = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                except Exception:
                    pub = None
            sent, _ = headline_sentiment(title)
            out.append(
                NewsItem(
                    id=uid("yahoo", url or title),
                    title=title,
                    publisher=publisher,
                    url=url,
                    published_at=iso_ist(pub) if pub else None,
                    sentiment=sent,
                    relevance=relevance_to_symbol(title, name, ysym),
                    yahoo_symbol=ysym,
                    meta=_meta(pub or datetime.now(timezone.utc), "Yahoo Finance News", True),
                )
            )
        return out

    def _google_rss(self, ysym: str, name: str | None, limit: int) -> list[NewsItem]:
        q = name or display_symbol(ysym)
        resp, _, _ = timed_get(
            "google_news",
            GOOGLE_RSS,
            params={"q": f"{q} stock", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
        )
        if resp is None:
            return []
        try:
            root = ET.fromstring(resp.text)
        except Exception:
            return []
        out: list[NewsItem] = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_s = item.findtext("pubDate")
            source = item.findtext("{http://www.google.com/schemas/sitemap-news/0.9}source")
            if source is None:
                src_el = item.find("source")
                source = src_el.text if src_el is not None else None
            pub = None
            if pub_s:
                try:
                    pub = parsedate_to_datetime(pub_s)
                except Exception:
                    pub = None
            if not title:
                continue
            sent, _ = headline_sentiment(title)
            out.append(
                NewsItem(
                    id=uid("gnews", link or title),
                    title=title,
                    publisher=source or "Google News",
                    url=link or None,
                    published_at=iso_ist(pub) if pub else None,
                    sentiment=sent,
                    relevance=relevance_to_symbol(title, name, ysym),
                    yahoo_symbol=ysym,
                    meta=_meta(pub or datetime.now(timezone.utc), "Google News RSS", True),
                )
            )
        return out


news_provider = NewsProvider()
