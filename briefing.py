"""Daily news briefing: fetch RSS + HN → OpenRouter → Resend."""

import html
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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

MODEL        = "google/gemini-2.5-flash"      # default (analysis-heavy sections)
MODEL_FAST   = "google/gemini-2.0-flash-001"  # cheaper (list-heavy sections)
MODEL_PRIORITISER = "anthropic/claude-opus-4.7"  # final pass: prioritise + format
# Sections that only need a bullet-list summary get the faster/cheaper model.
FAST_SECTIONS = {"Product Hunt", "Reddit", "Smart Home"}

PRIORITISER_PROMPT = """You are the final editor of a daily news briefing email.

You will receive the full draft briefing as markdown, organised by section. Rewrite it as a single, polished briefing email that:

1. Leads with a "## Top Stories" section containing the 3–6 most important items overall, ranked by importance to the reader. The reader's interests, in priority order, are:
   - AI (models, research, products, industry moves)
   - Vibe-coding (AI-assisted development tools, agents, IDEs)
   - New Apps and product launches
   - Breaking world news
   Other topics should appear only if genuinely significant.
2. Follows with the remaining sections (## headings) in order of relevance, dropping any section with nothing noteworthy left after the Top Stories pull.
3. Keeps every story formatted as `**[Full headline](url)**` followed by a single bullet `- **Context**: one concise sentence on why it matters`. Preserve original URLs exactly.
4. Removes duplicates, low-signal listicles, and pure opinion pieces.
5. Uses clean, modern, scannable markdown — no extra commentary, no preamble, no sign-off. Output only the markdown briefing."""
MAX_TOKENS   = 4096
OPENROUTER_MAX_RETRIES = 4
OPENROUTER_RETRY_DELAY = 5
OPENROUTER_RETRYABLE_CODES = {429, 500, 502, 503, 504}
MAX_LLM_WORKERS = 2
CUTOFF_HOURS = 24
MAX_PER_FEED  = 10   # max articles returned per individual feed URL
# Per-section caps applied after all feeds in a section are combined.
# Sections not listed here are capped at MAX_PER_FEED per feed with no
# combined cap (e.g. Smart Home: 2 feeds × 10 = up to 20 articles).
FEED_LIMITS   = {"Product Hunt": 5, "Technology": 25}
HN_COUNT     = 5
REDDIT_COUNT = 10
REDDIT_RSS   = "https://old.reddit.com/top/.rss?feed=515128bf93b37729df51403d57c58993fa172039&user=allyant&t=day"
SEEN_FILE    = pathlib.Path("seen.json")
SEEN_MAX_AGE = timedelta(days=7)   # evict URLs older than this

# ---------------------------------------------------------------------------
# Seen-URL deduplication (cross-run)
# ---------------------------------------------------------------------------

def load_seen():
    """Return {url: iso-timestamp} from seen.json, or {} if missing/corrupt."""
    try:
        return json.loads(SEEN_FILE.read_text())
    except Exception:
        return {}


def save_seen(seen):
    """Write seen dict to seen.json, evicting entries older than SEEN_MAX_AGE."""
    cutoff = (datetime.now(timezone.utc) - SEEN_MAX_AGE).isoformat()
    fresh = {url: ts for url, ts in seen.items() if ts >= cutoff}
    SEEN_FILE.write_text(json.dumps(fresh, indent=2))


def filter_seen(items, seen):
    """Remove items whose 'url' key already appears in seen; mark survivors."""
    now = datetime.now(timezone.utc).isoformat()
    new_items = []
    for item in items:
        url = item.get("url", "")
        if url and url not in seen:
            seen[url] = now
            new_items.append(item)
    return new_items


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
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"  WARN: could not fetch Hacker News: {e}")
        return []

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

def _retry_delay_from_error(error, attempt):
    retry_after = None
    headers = getattr(error, "headers", None)
    if headers:
        retry_after = headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), OPENROUTER_RETRY_DELAY * attempt)
        except ValueError:
            pass
    return OPENROUTER_RETRY_DELAY * attempt


def call_llm(system, user, model=None):
    payload = json.dumps({
        "model":      model or MODEL,
        "max_tokens": MAX_TOKENS,
        "messages":   [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }).encode()

    for attempt in range(1, OPENROUTER_MAX_RETRIES + 2):
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "Content-Type":  "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")
            is_retryable = error.code in OPENROUTER_RETRYABLE_CODES
            if not is_retryable or attempt > OPENROUTER_MAX_RETRIES:
                raise RuntimeError(
                    f"OpenRouter {error.code}: {body[:500] or error.reason}"
                ) from error
            delay = _retry_delay_from_error(error, attempt)
            print(
                f"  OpenRouter {error.code} ({error.reason}); "
                f"retrying in {delay:.1f}s [{attempt}/{OPENROUTER_MAX_RETRIES}]"
            )
            time.sleep(delay)
        except urllib.error.URLError as error:
            if attempt > OPENROUTER_MAX_RETRIES:
                raise RuntimeError(f"OpenRouter request failed: {error.reason}") from error
            delay = OPENROUTER_RETRY_DELAY * attempt
            print(
                f"  OpenRouter network error ({error.reason}); "
                f"retrying in {delay:.1f}s [{attempt}/{OPENROUTER_MAX_RETRIES}]"
            )
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------

def md_to_html(md):
    title_style = (
        "margin:16px 0 4px;font-size:16px;font-weight:600;"
        "line-height:1.4;color:#111;"
    )
    title_link_style = "color:#111;text-decoration:underline;"
    body_link_style = "color:#111;text-decoration:underline;"

    def inline(text, link_style=body_link_style):
        text = re.sub(
            r'\[([^\]]+)\]\((https?://[^\)]+)\)',
            rf'<a href="\2" style="{link_style}">\1</a>',
            text,
        )
        text = re.sub(r'(?<!["\(])(https?://\S+)',
                      rf'<a href="\1" style="{body_link_style}">\1</a>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',         text)
        return text

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    bold_link = re.compile(r'^\*\*\[.+?\]\(https?://[^\)]+\)\*\*')
    bold_text = re.compile(r'^\*\*[^*]+\*\*')

    out, in_list = [], False
    for line in md.split("\n"):
        s = line.strip()
        if line.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<h2 style="font-size:13px;font-weight:700;text-transform:uppercase;'
                       f'letter-spacing:.07em;color:#888;margin:36px 0 12px;'
                       f'padding-bottom:6px;border-bottom:2px solid #eee;">{esc(line[3:])}</h2>')
        elif line.startswith("# "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<h1 style="font-size:18px;font-weight:700;color:#000;margin:32px 0 10px;">'
                       f'{esc(line[2:])}</h1>')
        elif bold_link.match(s) or (bold_text.match(s) and not line.startswith("-")):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<p style="{title_style}">{inline(esc(s), link_style=title_link_style)}</p>')
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                out.append('<ul style="margin:2px 0 10px;padding-left:16px;list-style:none;">')
                in_list = True
            out.append(f'<li style="margin:2px 0;font-size:13px;color:#555;line-height:1.5;">'
                       f'{inline(esc(line[2:]))}</li>')
        elif not s or s == "---":
            if in_list:
                out.append("</ul>")
                in_list = False
            if not s:
                out.append('<div style="height:4px;"></div>')
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<p style="margin:0 0 8px;font-size:14px;color:#333;line-height:1.6;">'
                       f'{inline(esc(line))}</p>')

    if in_list:
        out.append("</ul>")
    return "\n".join(out)


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

def build_sections(cutoff, seen):
    """Return list of (section_name, content_str, article_count) tuples."""
    sections = []

    for section, urls in FEEDS.items():
        limit = FEED_LIMITS.get(section, MAX_PER_FEED)
        articles = []
        for url in urls:
            articles.extend(fetch_feed(url, cutoff))
        articles = filter_seen(articles[:limit], seen)
        if articles:
            lines = [f"## {section}"]
            for a in articles:
                lines.append(f"- [{a['title']}]({a['url']})")
            sections.append((section, "\n".join(lines), len(articles)))

    # Hacker News
    hn = filter_seen(fetch_hn(cutoff), seen)
    if hn:
        lines = ["## Hacker News"]
        for h in hn:
            lines.append(f"- [{h['title']}]({h['url']}) — {h['points']} points, {h['comments']} comments")
        sections.append(("Hacker News", "\n".join(lines), len(hn)))

    # Reddit (personal feed)
    reddit = filter_seen(fetch_reddit(cutoff), seen)
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
            sections.append(("Reddit", "\n".join(lines), len(lines) - 1))

    return sections


def main():
    t_start = time.time()
    cutoff  = datetime.now(timezone.utc) - timedelta(hours=CUTOFF_HOURS)
    now_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")

    seen = load_seen()
    print("Fetching articles...")
    t_fetch = time.time()
    sections = build_sections(cutoff, seen)
    save_seen(seen)
    article_count = sum(c for _, _, c in sections)
    print(f"Fetched {article_count} new articles across {len(sections)} sections in {time.time()-t_fetch:.1f}s")

    system = open("prompt.txt").read().strip()

    def call_section(args):
        section_name, content, count = args
        model = MODEL_FAST if section_name in FAST_SECTIONS else MODEL
        t = time.time()
        result = call_llm(system, content, model=model)
        print(f"  {section_name}: {count} articles → {model} ({time.time()-t:.1f}s)")
        return result

    worker_count = min(len(sections), MAX_LLM_WORKERS) or 1
    print(f"Calling OpenRouter ({worker_count} workers max)...")
    t_llm = time.time()

    with ThreadPoolExecutor(max_workers=worker_count) as ex:
        digest_parts = list(ex.map(call_section, sections))

    print(f"LLM calls done in {time.time()-t_llm:.1f}s")
    digest = "\n\n".join(digest_parts)
    print(f"Got {len(digest)} chars total")

    print(f"Prioritising + reformatting via {MODEL_PRIORITISER}...")
    t_pri = time.time()
    try:
        digest = call_llm(PRIORITISER_PROMPT, digest, model=MODEL_PRIORITISER)
        print(f"Prioritiser done in {time.time()-t_pri:.1f}s ({len(digest)} chars)")
    except Exception as e:
        print(f"  WARN: prioritiser failed ({e}); falling back to raw digest")

    print("--- Final digest (first 800 chars) ---")
    print(digest[:800])
    print("---")

    run_url = os.environ.get("RUN_URL", "")
    html    = wrap_email(md_to_html(digest), now_str, run_url)
    subject = f"Daily News Briefing — {now_str}"

    print("Sending email...")
    t_email = time.time()
    send_email(subject, html, digest)
    print(f"Email sent in {time.time()-t_email:.1f}s")
    print(f"Total pipeline time: {time.time()-t_start:.1f}s")


def send_failure_alert(error_msg):
    """Send a short alert email if the pipeline fails."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        print("No RESEND_API_KEY — cannot send failure alert")
        return
    payload = json.dumps({
        "from":    "Daily News <reports@infinitywave.design>",
        "to":      ["me@allisterantosik.com"],
        "subject": "Daily News pipeline failed",
        "text":    f"The daily news pipeline failed:\n\n{error_msg}",
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {resend_key}",
            "Content-Type":  "application/json",
            "User-Agent":    "curl/8.7.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            json.loads(r.read())
        print("Failure alert sent.")
    except Exception as e:
        print(f"Could not send failure alert: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        msg = traceback.format_exc()
        print(f"FATAL: {exc}\n{msg}")
        send_failure_alert(msg)
        raise
