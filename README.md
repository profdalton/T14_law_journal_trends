# De Novo — T14 Law Review Trend Tracker

A static site (GitHub Pages) that shows what the fourteen flagship
law reviews are publishing, grouped by topic, refreshed weekly by a
scheduled GitHub Action.

**Live now:** the site works today with sample placeholder data in
`data/articles.json`, so you can see the design before the scraper
runs. It's clearly marked `"Sample:"` and gets replaced automatically
the first time the scraper finds real articles.

## 1. Get it on GitHub Pages (5 minutes)

1. Create a new repository on GitHub (public — Pages' free tier needs
   that, unless you have GitHub Pro/Team/Enterprise).
2. Push everything in this folder to it.
3. In the repo, go to **Settings → Pages**. Under "Build and
   deployment," set **Source** to "Deploy from a branch," branch
   `main`, folder `/ (root)`. Save.
4. Your site is live in a minute or two at
   `https://<your-username>.github.io/<repo-name>/`.

That's it for hosting — no server, no build step, free.

## 2. Turn on the weekly scraper

The scraper (`scraper/scrape.py`) runs automatically via
`.github/workflows/weekly-scrape.yml` every Monday at 06:00 UTC, and
commits the results straight back to `data/articles.json`. You can
also trigger it manually any time from the **Actions** tab → "Weekly
journal scan" → **Run workflow**.

**Topic classification** defaults to free keyword matching
(`scraper/classify.py`). To switch on AI classification (recommended
— much better at ambiguous/interdisciplinary titles) for a few cents
a week:

1. Get an API key at [console.anthropic.com](https://console.anthropic.com).
2. In the repo, go to **Settings → Secrets and variables → Actions →
   New repository secret**. Name it `ANTHROPIC_API_KEY`, paste the
   key.
3. Nothing else to do — `scrape.py` picks it up automatically and
   only calls the API for genuinely new articles, so the ongoing cost
   stays small even years in.

## 3. Expect to tune the scraper (important)

Every law review's website has different HTML, and none of the
listing-page URLs or selectors in `scraper/journals.py` /
`scraper/scrape.py` have been tested against the live sites — they
were written from best knowledge of each journal's site, not
verified live. **Treat the first run as a shakedown, not a finished
product:**

1. Run it locally to see what's working:
   ```
   cd scraper
   pip install -r requirements.txt
   python scrape.py --dry-run
   ```
2. It prints, per journal, how many article links it found. Journals
   showing `0` need attention — open that journal's listing page,
   view source, and check what CSS selector actually wraps each
   article title. Add it to the `selectors` list in
   `extract_generic()` in `scrape.py`, or write a small
   journal-specific function if the site is unusual (e.g. loads
   articles via JavaScript, which `requests` can't execute — those
   need a different approach, like finding an RSS feed or API the
   site's front end calls).
3. Re-run `--dry-run` until the count looks right, then let the
   scheduled Action take over.

Budget an hour or two for this the first week, and expect the odd
selector to break again down the road when a journal redesigns its
site — a normal maintenance cadence for any scraper, not a sign
something's wrong with the setup.

## 4. Customize

- **Topics** — edit `data/topics.json` (site) and
  `scraper/classify.py`'s `TOPIC_KEYWORDS` (keyword fallback) to stay
  in sync. Order matters: it drives the Roman numerals on the site.
- **Journals** — add/remove entries in `scraper/journals.py`. To go
  beyond flagships (e.g. add a school's international-law journal or
  regulation journal), just add more entries — nothing else changes.
- **Colors/fonts** — all in `assets/style.css`, `:root` block at the
  top.
- **How far back articles stay listed** — `PRUNE_AFTER_DAYS` in
  `scrape.py` (default 120 days / ~4 months).
- **Article type** — where a journal's site exposes it (currently
  Yale, Georgetown, Michigan, and Penn), each article is tagged with
  its type (Article, Note, Essay, Comment, Review, etc.) in the
  `article_type` field, shown as a small badge on the card and
  available as a filter and export column. Left blank for journals
  whose listing pages don't expose this cleanly — extend the
  relevant `extract_*` function in `scrape.py` to add more.
- **Export** — the "Export CSV" / "Export JSON" buttons above the
  article list export whatever's currently filtered (not necessarily
  everything), so you can narrow to a topic or journal first, then
  export just that subset for external analysis.

## File map

```
index.html               the page itself
assets/style.css          all design tokens + styles
assets/app.js             loads data/*.json, renders filters + cards + trend chart
data/topics.json          topic taxonomy (ordered)
data/articles.json        the article database (scraper writes here)
data/topic-history.json   weekly topic-count snapshots, powers the trend chart
                           (one entry added automatically per real scrape.py run)
scraper/journals.py       journal list + listing-page URLs
scraper/classify.py       topic classification (AI or keyword)
scraper/scrape.py         the scan itself (--dry-run, --reclassify flags)
.github/workflows/        the weekly scheduled run
```

## Re-classifying existing articles

If you turn on AI classification (`ANTHROPIC_API_KEY`) after articles are
already in `data/articles.json`, they'll keep whatever topic the keyword
fallback gave them until re-scanned. To re-tag everything already in the
database without re-scraping any journal sites:

```
ANTHROPIC_API_KEY=your-key-here python3 scrape.py --reclassify
```

This does not touch `data/topic-history.json` or add a new weekly
snapshot — it's a one-off correction, not a scan.
