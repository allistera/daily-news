import asyncio
import json
import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastmcp import Client

# Europe/London handles the BST/GMT switch automatically.
UK = ZoneInfo("Europe/London")


def _build_client() -> Client:
    """Create the Product Hunt MCP client.

    Built lazily inside a function so that merely importing this module does
    not require ``PRODUCT_HUNT_TOKEN`` to be set or spin up the MCP server.
    """
    return Client({
        "mcpServers": {
            "product-hunt": {
                "command": "product-hunt-mcp",
                "env": {"PRODUCT_HUNT_TOKEN": os.environ["PRODUCT_HUNT_TOKEN"]},
            }
        }
    })


def _previous_day_window():
    """Return ``(posted_after, posted_before, day)`` for yesterday in UK time.

    The two timestamps are UTC ISO strings suitable for the ``get_posts`` API;
    ``day`` is the ``date`` being covered (for display).
    """
    today = datetime.now(UK).date()
    yesterday = today - timedelta(days=1)
    day_start = datetime.combine(yesterday, time.min, tzinfo=UK)
    day_end = datetime.combine(today, time.min, tzinfo=UK)
    posted_after = day_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    posted_before = day_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return posted_after, posted_before, yesterday


def previous_day():
    """Return yesterday's date in UK time — the window ``posts_for_email`` covers."""
    return _previous_day_window()[2]


async def _fetch(count: int = 20):
    posted_after, posted_before, _ = _previous_day_window()
    async with _build_client() as client:
        result = await client.call_tool(
            "get_posts",
            {
                "order": "VOTES",
                "posted_after": posted_after,
                "posted_before": posted_before,
                "count": count,  # max allowed is 20
            },
        )
        # Prefer the deserialized structured data; fall back to raw text content.
        if result.data is not None:
            return result.data
        return [getattr(block, "text", str(block)) for block in result.content]


def fetch_top_posts(count: int = 20):
    """Fetch the previous day's top Product Hunt posts (by votes).

    Returns the raw structured ``get_posts`` response. Safe to call from
    synchronous code such as ``send_email.py``.
    """
    return asyncio.run(_fetch(count))


def _extract_posts(data):
    """Pull the list of post objects out of a ``get_posts`` response."""
    if isinstance(data, dict):
        inner = data.get("data", data)
        if isinstance(inner, dict):
            return inner.get("posts") or []
    if isinstance(data, list):
        return data
    return []


def posts_for_email(count: int = 20) -> list[dict]:
    """Return the top posts as ``[{"title", "url"}, ...]`` for the email template."""
    items = []
    for post in _extract_posts(fetch_top_posts(count)):
        if not isinstance(post, dict):
            continue
        title = post.get("name") or post.get("tagline")
        url = post.get("url") or post.get("website")
        if title and url:
            items.append({"title": title, "url": url})
    return items


if __name__ == "__main__":
    _, _, yesterday = _previous_day_window()
    print(f"Top Product Hunt posts for {yesterday} (UK time, by votes):\n")
    print(json.dumps(fetch_top_posts(), indent=2, default=str))
