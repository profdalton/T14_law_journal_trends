"""
Journal source config.

Each entry needs:
  name   - display name, shown on the site
  slug   - short id, used in logs
  url    - a page that lists recent/current articles (issue page,
           "forthcoming" page, or blog index)
  rss    - optional RSS/Atom feed URL, tried first if present

IMPORTANT: these URLs are best-effort and NOT verified against live
scraping behavior (this project was built in a sandbox without access
to law-school domains). Treat the first run as a shakedown: run
`python scrape.py --dry-run` locally, see which journals return zero
articles, and open their site's HTML to fix the selector in
scrape.py's `extract_generic()` (or add a journal-specific function)
for that one. Sites also change their HTML periodically, so expect to
revisit this list every so often, not just once.
"""

JOURNALS = [
    {"name": "Yale Law Journal", "slug": "yale", "url": "https://www.yalelawjournal.org/forthcoming", "rss": None},
    {"name": "Harvard Law Review", "slug": "harvard", "url": "https://harvardlawreview.org/print/", "rss": None},
    {"name": "Stanford Law Review", "slug": "stanford", "url": "https://www.stanfordlawreview.org/print/", "rss": None},
    {"name": "University of Chicago Law Review", "slug": "uchicago", "url": "https://lawreview.uchicago.edu/print-archive", "rss": None},
    {"name": "Columbia Law Review", "slug": "columbia", "url": "https://columbialawreview.org/content-type/print/", "rss": None},
    {"name": "NYU Law Review", "slug": "nyu", "url": "https://www.nyulawreview.org/issues/", "rss": None},
    {"name": "University of Pennsylvania Law Review", "slug": "penn", "url": "https://www.pennlawreview.com/print/", "rss": None},
    {"name": "Virginia Law Review", "slug": "virginia", "url": "https://virginialawreview.org/articles/", "rss": None},
    {"name": "California Law Review", "slug": "berkeley", "url": "https://www.californialawreview.org/print/", "rss": None},
    {"name": "Michigan Law Review", "slug": "michigan", "url": "https://michiganlawreview.org/print-issues/", "rss": None},
    {"name": "Duke Law Journal", "slug": "duke", "url": "https://dlj.law.duke.edu/current-issue/", "rss": None},
    {"name": "Northwestern University Law Review", "slug": "northwestern", "url": "https://northwesternlawreview.org/print/", "rss": None},
    {"name": "Cornell Law Review", "slug": "cornell", "url": "https://www.cornelllawreview.org/print-edition/", "rss": None},
    {"name": "Georgetown Law Journal", "slug": "georgetown", "url": "https://www.law.georgetown.edu/georgetown-law-journal/print-editions/", "rss": None},
]
