"""
Classifies an article into one of the topics in data/topics.json.

Mode is chosen automatically:
  - If the ANTHROPIC_API_KEY environment variable is set, each new
    article is classified with a single small Claude call (cheap:
    short prompt, ~5-token answer). This gives much better accuracy,
    especially for ambiguous or interdisciplinary titles.
  - Otherwise, falls back to free keyword matching against
    TOPIC_KEYWORDS below. Good enough to start with zero cost/setup;
    edit the keyword lists any time to improve results.

Only NEW articles (not already in data/articles.json) are classified
each run, so the AI mode stays cheap even weekly over years.
"""

import os
import json
import urllib.request

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLASSIFY_MODEL = "claude-sonnet-4-6"

TOPIC_KEYWORDS = {
    "Constitutional Law": ["constitution", "first amendment", "due process", "equal protection", "separation of powers", "federalism", "fourteenth amendment"],
    "Administrative & Regulatory Law": ["agency", "administrative", "chevron", "rulemaking", "regulatory", "apa "],
    "Criminal Law & Procedure": ["criminal", "sentencing", "prosecut", "police", "fourth amendment", "bail", "incarcerat"],
    "Civil Procedure & Federal Courts": ["civil procedure", "standing", "jurisdiction", "federal courts", "class action", "discovery", "pleading"],
    "Corporate, Securities & Business Law": ["corporate", "securities", "shareholder", "merger", "antitrust", "business law", "bankruptcy"],
    "Law & Economics / Empirical Legal Studies": ["empirical", "econometric", "regression", "quantitative", "law and economics", "dataset"],
    "International & Comparative Law": ["international law", "treaty", "comparative law", "extraterritorial", "foreign relations", "human rights"],
    "Intellectual Property & Technology Law": ["patent", "copyright", "trademark", "artificial intelligence", "algorithm", "privacy", "data protection", "technology law"],
    "Environmental & Energy Law": ["environmental", "climate", "energy law", "emissions", "epa "],
    "Tax Law": ["tax ", "taxation", "irs", "revenue code"],
    "Labor & Employment Law": ["labor law", "employment", "union", "workplace", "worker"],
    "Race, Law & Society": ["race", "racial", "civil rights", "discrimination", "critical race"],
    "Health & Family Law": ["health law", "family law", "reproductive", "medicaid", "healthcare", "custody"],
    "Legal Theory & Jurisprudence": ["jurisprudence", "legal theory", "philosophy of law", "interpretation", "originalism", "legal history"],
}

DEFAULT_TOPIC = "Legal Theory & Jurisprudence"


def classify_keyword(title, snippet, topics):
    text = f"{title} {snippet}".lower()
    best_topic, best_score = None, 0
    for topic in topics:
        keywords = TOPIC_KEYWORDS.get(topic, [])
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic or DEFAULT_TOPIC


def classify_ai(title, snippet, topics):
    prompt = (
        "Classify this law journal article into exactly one topic from the list. "
        "Reply with ONLY the topic string, exactly as written in the list, nothing else.\n\n"
        f"Topics:\n" + "\n".join(f"- {t}" for t in topics) + "\n\n"
        f"Title: {title}\nAbstract/snippet: {snippet or '(none provided)'}"
    )
    body = json.dumps({
        "model": CLASSIFY_MODEL,
        "max_tokens": 30,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        answer = data["content"][0]["text"].strip()
        # Match loosely in case of stray punctuation/casing
        for t in topics:
            if t.lower() in answer.lower() or answer.lower() in t.lower():
                return t
    except Exception as e:
        print(f"  [classify] AI call failed ({e}); falling back to keywords")
    return classify_keyword(title, snippet, topics)


def classify(title, snippet, topics):
    if ANTHROPIC_API_KEY:
        return classify_ai(title, snippet, topics)
    return classify_keyword(title, snippet, topics)
