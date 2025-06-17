#!/usr/bin/env python3
"""
news_fetcher.py  ·  ingest helper for ai24tv
------------------------------------------------------------
pip install requests gnews feedparser
(optional) export NEWSAPI_KEY="..."  # for the NewsAPI engine
------------------------------------------------------------
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Dict, Optional
import os, sys, json, pathlib, argparse, logging, urllib.parse, time

import requests
from gnews import GNews           # pip install gnews>=0.5
import feedparser                 # pip install feedparser


# ---------------------------------------------------------------------
# Option A – NewsAPI.org (needs free key)
# ---------------------------------------------------------------------
def fetch_news_newsapi(
    api_key: Optional[str] = None,
    query: str = "top headlines",
    language: str = "en",
    page_size: int = 20,
) -> List[Dict]:
    api_key = api_key or os.getenv("NEWSAPI_KEY")
    if not api_key:
        raise ValueError("Set NEWSAPI_KEY env var or pass --newsapi-key")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "apiKey": api_key,
    }

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    articles = resp.json().get("articles", [])

    return [
        {
            "source": a["source"]["name"],
            "title": a["title"],
            "description": a["description"],
            "url": a["url"],
            "image": a["urlToImage"],
            "published_at": a["publishedAt"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        for a in articles
    ]


# ---------------------------------------------------------------------
# Option B – GNews wrapper (no key)  +  RSS fallback (“force fetch”)
# ---------------------------------------------------------------------
def _fallback_to_rss(
    query: str,
    language: str,
    country: str,
    max_results: int,
) -> List[Dict]:
    """Direct Google-News RSS pull (no throttling guard, so be polite)."""
    rss_url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode(
            {
                "q": query,
                "hl": f"{language}-{country}",
                "gl": country,
                "ceid": f"{country}:{language}",
            }
        )
    )
    feed = feedparser.parse(rss_url)
    return [
        {
            "source": e.get("source", {}).get("title", ""),
            "title": e.title,
            "description": getattr(e, "summary", ""),
            "url": e.link,
            "image": None,
            "published_at": getattr(e, "published", None),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        for e in feed.entries[:max_results]
    ]


def fetch_news_gnews(
    query: str = "World",
    language: str = "en",
    country: str = "US",
    period: str = "7d",
    max_results: int = 10,
    force_fallback: bool = False,
    sleep_sec: float = 0.0,
) -> List[Dict]:
    """
    Fetches via gnews; falls back to raw RSS if nothing returns
    or if `force_fallback` is True.
    """
    gn = GNews(
        language=language,
        country=country,
        period=period,
        max_results=max_results,
    )

    raw: List[Dict] = []
    if not force_fallback:
        try:
            raw = gn.get_news(query) or []
        except Exception as exc:
            logging.warning("gnews threw %s – switching to RSS fallback", exc)

    # RSS fallback path
    if force_fallback or not raw:
        raw = _fallback_to_rss(query, language, country, max_results)

    # normalise field names for downstream consistency
    normalised = []
    for a in raw:
        normalised.append(
            {
                "source": a.get("source") or a.get("publisher"),
                "title": a["title"],
                "description": a.get("description", ""),
                "url": a["url"],
                "image": a.get("image"),
                "published_at": a.get("published_at")
                or a.get("published date")
                or a.get("published"),
                "fetched_at": a.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
            }
        )

    if sleep_sec:
        time.sleep(sleep_sec)

    return normalised


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch news articles and output JSON (stdout or file)."
    )
    p.add_argument(
        "-e",
        "--engine",
        choices=["gnews", "newsapi"],
        default="gnews",
        help="Backend to use (default: gnews).",
    )
    p.add_argument("-q", "--query", default="World", help="Search phrase.")
    p.add_argument("-l", "--language", default="en", help="ISO 639-1 language.")
    p.add_argument("-c", "--country", default="US", help="ISO 3166-1 country.")
    p.add_argument(
        "--period",
        default="7d",
        help="Look-back window for gnews (e.g. 1d, 30d, 1y).",
    )
    p.add_argument(
        "-n",
        "--max",
        type=int,
        default=20,
        help="Max articles (gnews: reliable ≤10, NewsAPI: ≤100).",
    )
    p.add_argument(
        "-o",
        "--output",
        help="Write JSON to file instead of stdout.",
    )
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    p.add_argument(
        "--newsapi-key",
        help="Override NEWSAPI_KEY env var (NewsAPI engine only).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Force RSS fallback even if gnews returns results.",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep after fetch (rate-limit helper).",
    )
    return p


def _output_json(data: List[Dict], pretty: bool, outfile: Optional[str]):
    dump_kwargs = {"indent": 2, "ensure_ascii": False} if pretty else {}
    if outfile:
        path = pathlib.Path(outfile).expanduser()
        path.write_text(json.dumps(data, **dump_kwargs), encoding="utf-8")
        print(f"Saved {len(data)} article(s) → {path}")
    else:
        sys.stdout.write(json.dumps(data, **dump_kwargs) + "\n")


def main() -> None:
    args = _build_arg_parser().parse_args()

    if args.engine == "gnews":
        articles = fetch_news_gnews(
            query=args.query,
            language=args.language,
            country=args.country,
            period=args.period,
            max_results=args.max,
            force_fallback=args.force,
            sleep_sec=args.sleep,
        )
    else:  # NewsAPI
        articles = fetch_news_newsapi(
            api_key=args.newsapi_key,
            query=args.query,
            language=args.language,
            page_size=args.max,
        )

    _output_json(articles, pretty=args.pretty, outfile=args.output)


if __name__ == "__main__":
    main()
