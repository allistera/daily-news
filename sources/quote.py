import json
import os
import urllib.parse
import urllib.request

# API Ninjas "Quotes" endpoint: https://api-ninjas.com/api/quotes
API_NINJAS_QUOTES_URL = "https://api.api-ninjas.com/v1/quotes"


def _build_request(category: str | None = None) -> urllib.request.Request:
    """Build the API Ninjas quotes request.

    Built lazily inside a function so that merely importing this module does
    not require ``API_NINJAS_KEY`` to be set. ``category`` is an optional,
    premium-only filter; without it the API returns a random quote (free tier).
    """
    url = API_NINJAS_QUOTES_URL
    if category:
        url = f"{url}?{urllib.parse.urlencode({'category': category})}"
    req = urllib.request.Request(url)
    req.add_header("X-Api-Key", os.environ["API_NINJAS_KEY"])
    req.add_header("User-Agent", "daily-news-bot")
    return req


def fetch_quote(category: str | None = None):
    """Fetch a quote from API Ninjas.

    Returns the raw response (a list of quote objects). Safe to call from
    synchronous code such as ``send_email.py``.
    """
    with urllib.request.urlopen(_build_request(category), timeout=30) as resp:
        return json.load(resp)


def _extract_quote(data):
    """Return the first quote object from a quotes response, or ``None``.

    The endpoint replies with a single-element list, but tolerate a bare object
    too in case the shape ever changes.
    """
    if isinstance(data, list):
        data = data[0] if data else None
    return data if isinstance(data, dict) else None


def quote_for_email(category: str | None = None) -> dict | None:
    """Return ``{"quote", "author"}`` for the masthead epigraph, or ``None``.

    ``None`` means there was nothing usable to show (so the caller can fall back
    to its own quote); network/auth errors propagate so the caller can log them.
    """
    record = _extract_quote(fetch_quote(category))
    if not record:
        return None
    quote = record.get("quote")
    if not quote:
        return None
    return {"quote": quote, "author": record.get("author") or ""}


if __name__ == "__main__":
    print(json.dumps(fetch_quote(), indent=2, default=str))
