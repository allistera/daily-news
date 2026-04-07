"""Daily news briefing: fetch RSS + HN → OpenRouter → Resend."""

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FEEDS = {
    "World News": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://www.theguardian.com/world/rss",
        "https://www.dailymail.co.uk/news/index.rss",
    ],
    "Technology": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://www.theregister.com/headlines.rss",
        "https://www.engadget.com/rss.xml",
        "https://venturebeat.com/feed/",
    ],
    "Product Hunt": [
        "https://www.producthunt.com/feed",
    ],
    "Smart Home": [
        "https://www.theverge.com/rss/smart-home/index.xml",
        "https://www.cnet.com/rss/smart-home/",
    ],
}

MODEL        = "google/gemini-2.5-flash"
MAX_TOKENS   = 4096
CUTOFF_HOURS = 24
MAX_PER_FEED  = 10   # articles per feed passed to Claude
FEED_LIMITS   = {"Product Hunt": 5, "Technology": 25}
HN_COUNT     = 5
REDDIT_COUNT = 10
REDDIT_RSS   = "https://old.reddit.com/top/.rss?feed=515128bf93b37729df51403d57c58993fa172039&user=allyant&t=day"

# ---------------------------------------------------------------------------
# RSS helpers
# ---------------------------------------------------------------------------

NS = {"dc": "http://purl.org/dc/elements/1.1/", "atom": "http://www.w3.org/2005/Atom"}

def _parse_date(text):
    """Parse RFC 2822 or ISO 8601 date strings; return UTC-aware datetime or None."""
    if not text:
        return None
    text = text.strip()
    # RFC 2822 (most RSS feeds)
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(text).astimezone(timezone.utc)
    except Exception:
        pass
    # ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[:len(fmt)], fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


RSS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def fetch_feed(url, cutoff):
    """Return list of {title, url} dicts published after cutoff."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": RSS_UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"  WARN: could not fetch {url}: {e}")
        return []

    # Support both RSS <item> and Atom <entry>
    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    results = []
    for item in items:
        # Date
        raw_date = (
            item.findtext("pubDate")
            or item.findtext("dc:date", namespaces=NS)
            or item.findtext("{http://www.w3.org/2005/Atom}updated")
            or item.findtext("{http://www.w3.org/2005/Atom}published")
        )
        dt = _parse_date(raw_date)
        if dt and dt < cutoff:
            continue

        # Title
        title = (
            item.findtext("title")
            or item.findtext("{http://www.w3.org/2005/Atom}title")
            or ""
        ).strip()

        # Link
        link = item.findtext("link") or ""
        if not link:
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.get("href", "")
        link = link.strip()

        if title and link:
            results.append({"title": title, "url": link})

    return results[:MAX_PER_FEED]


# ---------------------------------------------------------------------------
# Hacker News (Algolia)
# ---------------------------------------------------------------------------

def fetch_hn(cutoff):
    since = int(cutoff.timestamp())
    url = (
        f"https://hn.algolia.com/api/v1/search_by_date"
        f"?tags=story&numericFilters=created_at_i>{since}&hitsPerPage=200"
    )
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())

    hits = sorted(data["hits"], key=lambda h: h.get("points", 0), reverse=True)[:HN_COUNT]
    return [
        {
            "title":    h.get("title", "Untitled"),
            "url":      f"https://news.ycombinator.com/item?id={h['objectID']}",
            "points":   h.get("points", 0),
            "comments": h.get("num_comments", 0),
        }
        for h in hits
    ]


# ---------------------------------------------------------------------------
# Reddit (personal RSS feed)
# ---------------------------------------------------------------------------

def _reddit_sub_from_url(url):
    m = re.search(r"/r/([^/]+)/", url or "")
    return m.group(1) if m else "?"


def _reddit_parse_stats(description_html):
    """Best-effort score and comment counts from Reddit RSS <description> HTML."""
    text = html.unescape(description_html or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    score_m = re.search(r"([\d,]+)\s+points?", text, re.I)
    comments_m = re.search(r"([\d,]+)\s+comments?", text, re.I)
    score = score_m.group(1).replace(",", "") if score_m else "?"
    comments = comments_m.group(1).replace(",", "") if comments_m else "?"
    return score, comments


def fetch_reddit(cutoff):
    """Fetch posts from the user's personal Reddit RSS feed (enriched metadata)."""
    try:
        req = urllib.request.Request(REDDIT_RSS, headers={"User-Agent": RSS_UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"  WARN: could not fetch Reddit: {e}")
        return []

    # Reddit personal feeds are Atom in most cases, but support RSS too.
    entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

    results = []
    for item in entries:
        raw_date = (
            item.findtext("pubDate")
            or item.findtext("{http://www.w3.org/2005/Atom}updated")
            or item.findtext("{http://www.w3.org/2005/Atom}published")
            or ""
        )
        dt = _parse_date(raw_date)
        if dt and dt < cutoff:
            continue

        title = (
            item.findtext("title")
            or item.findtext("{http://www.w3.org/2005/Atom}title")
            or ""
        ).strip()
        link = (item.findtext("link") or "").strip()
        if not link:
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = (link_el.get("href") or "").strip()
        if not title or not link:
            continue

        desc = (
            item.findtext("description")
            or item.findtext("{http://www.w3.org/2005/Atom}content")
            or item.findtext("{http://www.w3.org/2005/Atom}summary")
            or ""
        )
        score, comments = _reddit_parse_stats(desc)
        results.append({
            "title":    title,
            "url":      link,
            "sub":      _reddit_sub_from_url(link),
            "score":    score,
            "comments": comments,
        })

    return results[:REDDIT_COUNT]


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------

def call_llm(system, user):
    payload = json.dumps({
        "model":      MODEL,
        "max_tokens": MAX_TOKENS,
        "messages":   [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type":  "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------

def md_to_html(md):
    def inline(text):
        text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
                      r'<a href="\2" style="color:#111;text-decoration:underline;">\1</a>', text)
        text = re.sub(r'(?<!["\(])(https?://\S+)',
                      r'<a href="\1" style="color:#555;text-decoration:underline;">\1</a>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',         text)
        return text

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    bold_link = re.compile(r'^\*\*\[.+\]\(https?://.+\)\*\*$')
    bold_text = re.compile(r'^\*\*[^*]+\*\*$')

    html, in_list = [], False
    for line in md.split("\n"):
        s = line.strip()
        if line.startswith("## "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f'<h2 style="font-size:13px;font-weight:700;text-transform:uppercase;'
                        f'letter-spacing:.07em;color:#888;margin:36px 0 12px;'
                        f'padding-bottom:6px;border-bottom:2px solid #eee;">{esc(line[3:])}</h2>')
        elif line.startswith("# "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f'<h1 style="font-size:18px;font-weight:700;color:#000;margin:32px 0 10px;">'
                        f'{esc(line[2:])}</h1>')
        elif bold_link.match(s) or (bold_text.match(s) and not line.startswith("-")):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f'<p style="margin:16px 0 4px;font-size:16px;font-weight:600;line-height:1.4;">'
                        f'{inline(esc(s))}</p>')
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html.append('<ul style="margin:2px 0 10px;padding-left:16px;list-style:none;">')
                in_list = True
            html.append(f'<li style="margin:2px 0;font-size:13px;color:#555;line-height:1.5;">'
                        f'{inline(esc(line[2:]))}</li>')
        elif not s or s == "---":
            if in_list: html.append("</ul>"); in_list = False
            if not s: html.append('<div style="height:4px;"></div>')
        else:
            if in_list: html.append("</ul>"); in_list = False
            html.append(f'<p style="margin:0 0 8px;font-size:14px;color:#333;line-height:1.6;">'
                        f'{inline(esc(line))}</p>')

    if in_list:
        html.append("</ul>")
    return "\n".join(html)


def wrap_email(body_html, date_str, run_url):
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#fff;">
  <div style="max-width:620px;margin:0 auto;padding:40px 32px;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif;
              font-size:14px;color:#333;">
    <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#aaa;">Daily Briefing</p>
    <h1 style="margin:0 0 4px;font-size:22px;font-weight:700;color:#000;">{date_str}</h1>
    <div style="height:1px;background:#eee;margin:20px 0 24px;"></div>
    {body_html}
    <div style="height:1px;background:#eee;margin:32px 0 20px;"></div>
    <p style="margin:0;font-size:11px;color:#bbb;">
      <a href="{run_url}" style="color:#bbb;">View run →</a>
    </p>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Resend
# ---------------------------------------------------------------------------

def send_email(subject, html, text):
    payload = json.dumps({
        "from":    "Daily News <reports@infinitywave.design>",
        "to":      ["me@allisterantosik.com"],
        "subject": subject,
        "html":    html,
        "text":    text,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization":  f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type":   "application/json",
            "User-Agent":     "curl/8.7.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Resend {e.code}: {body}") from e
    if "id" not in resp:
        raise RuntimeError(f"Unexpected Resend response: {resp}")
    print(f"Email sent. Resend ID: {resp['id']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_content(cutoff):
    sections = []

    for section, urls in FEEDS.items():
        limit = FEED_LIMITS.get(section, MAX_PER_FEED)
        articles = []
        for url in urls:
            articles.extend(fetch_feed(url, cutoff))
        articles = articles[:limit]
        if articles:
            lines = [f"## {section}"]
            for a in articles:
                lines.append(f"- [{a['title']}]({a['url']})")
            sections.append("\n".join(lines))

    # Hacker News
    hn = fetch_hn(cutoff)
    if hn:
        lines = ["## Hacker News"]
        for h in hn:
            lines.append(f"- [{h['title']}]({h['url']}) — {h['points']} points, {h['comments']} comments")
        sections.append("\n".join(lines))

    # Reddit (personal feed)
    reddit = fetch_reddit(cutoff)
    if reddit:
        lines = ["## Reddit"]
        for post in reddit:
            title = post.get("title", "").strip()
            url = post.get("url", "").strip()
            if not title or not url:
                continue
            sub = post.get("sub", "?")
            score = post.get("score", "?")
            comments = post.get("comments", "?")
            lines.append(
                f"- [{title}]({url}) — r/{sub}, {score} upvotes, {comments} comments"
            )
        if len(lines) > 1:
            sections.append("\n".join(lines))

    return "\n\n".join(sections)


def main():
    cutoff  = datetime.now(timezone.utc) - timedelta(hours=CUTOFF_HOURS)
    now_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")

    print("Fetching articles...")
    content = build_content(cutoff)
    print(f"Fetched {content.count(chr(10))} lines of content")

    system = open("prompt.txt").read().strip()

    print("Calling OpenRouter...")
    digest = call_llm(system, content)
    print(f"Got {len(digest)} chars from Claude")
    print("--- LLM output (first 800 chars) ---")
    print(digest[:800])
    print("---")

    run_url = os.environ.get("RUN_URL", "")
    html    = wrap_email(md_to_html(digest), now_str, run_url)
    subject = f"Daily News Briefing — {now_str}"

    print("Sending email...")
    send_email(subject, html, digest)


if __name__ == "__main__":
    main()
