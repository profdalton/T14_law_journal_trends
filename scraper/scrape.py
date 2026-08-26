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
RECLASSIFY = "--reclassify" in sys.argv


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
        "a[rel='bookmark']",  # Drupal-style sites (e.g. UChicago Law Review):
                              # <a rel="bookmark"><span class="field--name-title">Title</span></a>
        "a.article-link",  # card-style sites (e.g. Penn Law Review):
                           # <a class="article-link"><h2>Title</h2><p>author</p>...</a>
        "h4 a",  # e.g. Virginia Law Review's article feed
        "h1.blog-title a",  # e.g. California Law Review (Squarespace-style)
        "h2.IssueMini-title a",  # e.g. Northwestern University Law Review
        "p a:has(strong)",  # e.g. Georgetown Law Journal: <p><a><strong>Title</strong></a></p>
    ]
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href")
            # If the link wraps a heading plus other content (author,
            # abstract, tags), use just the heading's text as the
            # title instead of the whole link's (mixed) text.
            heading = a.find(["h1", "h2", "h3", "h4"])
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            if not href or not title or len(title) < 8:
                continue
            url = urljoin(base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append({"title": title, "url": url})

    return candidates


def extract_yale(html, base_url):
    """
    Yale's issue page dumps every volume back to 2000 into one page
    (all hidden behind an accordion, but present in the raw HTML).
    Scope extraction to just the first volume_wrapper -- the current
    volume -- instead of grabbing the entire 25-year archive.
    """
    soup = BeautifulSoup(html, "html.parser")
    first_volume = soup.select_one(".volume_wrapper")
    if not first_volume:
        return []
    candidates = []
    seen_urls = set()
    for a in first_volume.select("h3.leading-relaxed a"):
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


def extract_nyu(base_url):
    """
    NYU's /issues/ page only lists links to each volume/issue (e.g.
    /issues/volume-101-number-3/) -- it has no article titles itself.
    Follow the first (most recent) issue link, then extract from
    that page, where articles match the generic 'article h3 a' selector.
    """
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [nyu] fetch failed: {e}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    issue_url = None
    for a in soup.select("a[href]"):
        href = a["href"]
        if re.search(r"volume-\d+-number-\d+/?$", href):
            issue_url = urljoin(base_url, href)
            break
    if not issue_url:
        print("  [nyu] couldn't find a current-issue link on the index page")
        return []
    try:
        resp2 = requests.get(issue_url, headers=HEADERS, timeout=20)
        resp2.raise_for_status()
    except Exception as e:
        print(f"  [nyu] fetch of issue page failed: {e}")
        return []
    return extract_generic(resp2.text, issue_url)


def extract_virginia(html, base_url):
    """
    Virginia Law Review's /print/ page uses <h4><a>Title</a></h4>
    for every article in its entire multi-decade archive, not just
    the current volume -- so the generic 'h4 a' selector way
    overshoots (hundreds of hits). Scope to just the entries that
    have the accompanying '.article-feed-author' marker immediately
    after them, and cap defensively in case that's still broad.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    seen_urls = set()
    for marker in soup.select(".article-feed-author"):
        h4 = None
        for sib in marker.find_previous_siblings():
            if sib.name == "h4":
                h4 = sib
                break
        if not h4:
            continue
        a = h4.find("a")
        if not a:
            continue
        href = a.get("href")
        title = a.get_text(strip=True)
        if not href or not title or len(title) < 8:
            continue
        url = urljoin(base_url, href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append({"title": title, "url": url})
    return candidates[:30]  # safety cap: no current volume should exceed this


def extract_michigan(base_url):
    """
    Michigan's /archive/ page links to individual issue pages
    (/volume/volNNN-issN/) rather than listing articles directly.
    Follow the first (most recent) issue link, then extract titles
    from that page's '.box__title a' pattern.
    """
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [michigan] fetch failed: {e}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    issue_url = None
    for a in soup.select("a[href]"):
        href = a["href"]
        if re.search(r"/volume/vol\d+-iss\d+/?$", href):
            issue_url = urljoin(base_url, href)
            break
    # If /archive/ itself redirected straight to an issue page (as it
    # did when checked manually), the page we already fetched IS the
    # issue page -- extract directly from it instead of failing.
    target_html = resp.text
    target_url = base_url
    if issue_url and issue_url != base_url:
        try:
            resp2 = requests.get(issue_url, headers=HEADERS, timeout=20)
            resp2.raise_for_status()
            target_html, target_url = resp2.text, issue_url
        except Exception as e:
            print(f"  [michigan] fetch of issue page failed: {e}")
    soup2 = BeautifulSoup(target_html, "html.parser")
    candidates = []
    seen_urls = set()
    for a in soup2.select(".box__title a"):
        href = a.get("href")
        title = a.get_text(strip=True)
        if not href or not title or len(title) < 8:
            continue
        url = urljoin(target_url, href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append({"title": title, "url": url})
    return candidates


def extract_duke(html, base_url):
    """
    Duke Law Journal's current-issue page uses a bare <h4>Title</h4>
    with no link inside it -- the actual link (to a PDF citation) is
    in the next <p> sibling instead. Stitch the two together.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    seen_urls = set()
    for h4 in soup.find_all("h4"):
        title = h4.get_text(strip=True)
        if not title or len(title) < 8:
            continue
        sib = h4.find_next_sibling("p")
        if not sib:
            continue
        a = sib.find("a")
        if not a:
            continue
        href = a.get("href")
        if not href:
            continue
        url = urljoin(base_url, href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append({"title": title, "url": url})
    return candidates


def fetch_journal(journal):
    if journal["slug"] == "nyu":
        return extract_nyu(journal["url"])
    if journal["slug"] == "michigan":
        return extract_michigan(journal["url"])
    try:
        resp = requests.get(journal["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [{journal['slug']}] fetch failed: {e}")
        return []
    if journal["slug"] == "yale":
        return extract_yale(resp.text, journal["url"])
    if journal["slug"] == "virginia":
        return extract_virginia(resp.text, journal["url"])
    if journal["slug"] == "duke":
        return extract_duke(resp.text, journal["url"])
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

    if RECLASSIFY:
        # One-off: re-run classification on every article already in
        # data/articles.json (e.g. after turning on AI classification,
        # to fix articles that were tagged by the free keyword
        # fallback before the ANTHROPIC_API_KEY secret was added).
        # Does not fetch any journal sites.
        articles = existing.get("articles", [])
        print(f"Reclassifying {len(articles)} existing articles...")
        changed = 0
        for i, a in enumerate(articles, 1):
            new_topic = classify(a["title"], a.get("snippet", ""), topics)
            if new_topic != a.get("topic"):
                changed += 1
            a["topic"] = new_topic
            if i % 20 == 0:
                print(f"  {i}/{len(articles)}...")
        print(f"Done. {changed} article(s) got a different topic.")
        output = {
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "articles": articles,
        }
        if DRY_RUN:
            print("[dry run] not writing data/articles.json")
        else:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"Wrote {DATA_FILE}")
        return

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
