#!/usr/bin/env python3
"""
Weekly scan: for each journal in journals.py, pull the listing page,
extract candidate articles, classify any that are new, and merge
them into ../data/articles.json.

Run locally:   python scrape.py
Dry run (no file write, verbose): python scrape.py --dry-run

Run automatically every Monday via .github/workflows/weekly-scrape.yml
"""

import sys
import json
import re
import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from journals import JOURNALS
from classify import classify

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "articles.json"
TOPICS_FILE = ROOT / "data" / "topics.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TheDocketBot/1.0; +https://github.com/)"}
PRUNE_AFTER_DAYS = 120  # drop articles older than ~4 months to keep the site current
DRY_RUN = "--dry-run" in sys.argv


def load_json(path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def extract_generic(html, base_url):
    """
    Heuristic extractor for WordPress/Scholastica-style journal sites:
    looks for headline-shaped links (article/entry title classes, or
    <h2>/<h3> wrapping an <a>). Titles-only extraction: authors/dates
    are frequently on the article's own page, not the listing page, so
    this returns what's available and leaves the rest blank rather
    than guessing.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    seen_urls = set()

    selectors = [
        "h2.entry-title a", "h3.entry-title a", ".entry-title a",
        "h2.post-title a", ".post-title a",
        "article h2 a", "article h3 a",
        ".article-title a", ".card-title a",
    ]
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href")
            title = a.get_text(strip=True)
            if not href or not title or len(title) < 8:
                continue
            url = urljoin(base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append({"title": title, "url": url})

    return candidates


def fetch_journal(journal):
    try:
        resp = requests.get(journal["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [{journal['slug']}] fetch failed: {e}")
        return []
    return extract_generic(resp.text, journal["url"])


def prune_old(articles):
    cutoff = datetime.date.today() - datetime.timedelta(days=PRUNE_AFTER_DAYS)
    kept = []
    for a in articles:
        try:
            d = datetime.date.fromisoformat(a.get("date", ""))
            if d < cutoff:
                continue
        except ValueError:
            pass  # keep entries with unparseable/missing dates
        kept.append(a)
    return kept


def main():
    topics = load_json(TOPICS_FILE, {"topics": []})["topics"]
    existing = load_json(DATA_FILE, {"articles": []})
    existing_urls = {a["url"] for a in existing.get("articles", []) if a.get("url")}

    new_articles = []
    for journal in JOURNALS:
        print(f"Scanning {journal['name']}...")
        found = fetch_journal(journal)
        fresh = [f for f in found if f["url"] not in existing_urls]
        print(f"  {len(found)} links found, {len(fresh)} new")

        for item in fresh:
            topic = classify(item["title"], "", topics)
            new_articles.append({
                "title": item["title"],
                "authors": "",
                "journal": journal["name"],
                "topic": topic,
                "url": item["url"],
                "date": datetime.date.today().isoformat(),
                "snippet": "",
            })
            existing_urls.add(item["url"])

    merged = existing.get("articles", []) + new_articles
    merged = [a for a in merged if not a.get("title", "").startswith("Sample:")]  # drop seed data once real data arrives
    merged = prune_old(merged)

    output = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "articles": merged,
    }

    print(f"\nTotal new articles this run: {len(new_articles)}")
    print(f"Total articles kept (after pruning >{PRUNE_AFTER_DAYS}d): {len(merged)}")

    if DRY_RUN:
        print("[dry run] not writing data/articles.json")
    else:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Wrote {DATA_FILE}")


if __name__ == "__main__":
    main()
