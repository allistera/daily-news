import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# Europe/London handles the BST/GMT switch automatically.
UK = ZoneInfo("Europe/London")

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


def _build_request(query: str, count: int) -> urllib.request.Request:
    """Build the GitHub repository-search request.

    Built lazily inside a function so that merely importing this module does
    not reach out to the network. ``GITHUB_TOKEN`` is used when present (for
    higher rate limits) but is optional.
    """
    params = urllib.parse.urlencode(
        {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": count,  # GitHub allows up to 100
        }
    )
    req = urllib.request.Request(f"{GITHUB_SEARCH_URL}?{params}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "daily-news-bot")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return req


def previous_day():
    """Return yesterday's date in UK time — the window the fetchers default to."""
    return datetime.now(UK).date() - timedelta(days=1)


def _day_window(day):
    """Return ``(after, before)`` UTC ISO bounds spanning the given UK calendar day."""
    day_start = datetime.combine(day, time.min, tzinfo=UK)
    day_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=UK)
    after = day_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = day_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return after, before


def fetch_top_repos(count: int = 20, day=None):
    """Fetch the most-starred new GitHub repos for ``day`` (default: yesterday, UK).

    Returns the raw GitHub search response. Safe to call from synchronous code
    such as ``send_email.py``.
    """
    created_after, created_before = _day_window(day or previous_day())
    query = f"created:{created_after}..{created_before}"
    with urllib.request.urlopen(_build_request(query, count), timeout=30) as resp:
        return json.load(resp)


def _extract_repos(data):
    """Return the list of repository objects from a search response."""
    if isinstance(data, dict):
        return data.get("items") or []
    if isinstance(data, list):
        return data
    return []


def repos_for_email(count: int = 20, day=None) -> list[dict]:
    """Return the top repos as ``[{"title", "url"}, ...]`` for the email template."""
    items = []
    for repo in _extract_repos(fetch_top_repos(count, day)):
        if not isinstance(repo, dict):
            continue
        title = repo.get("full_name") or repo.get("name")
        url = repo.get("html_url") or repo.get("url")
        if title and url:
            items.append({"title": title, "url": url})
    return items


if __name__ == "__main__":
    print(f"Top GitHub repos for {previous_day()} (UK time, by stars):\n")
    print(json.dumps(fetch_top_repos(), indent=2, default=str))
