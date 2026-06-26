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
    return Client(
        {
            "mcpServers": {
                "product-hunt": {
                    "command": "product-hunt-mcp",
                    "env": {"PRODUCT_HUNT_TOKEN": os.environ["PRODUCT_HUNT_TOKEN"]},
                }
            }
        }
    )


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


async def _fetch(count, day):
    posted_after, posted_before = _day_window(day)
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


def fetch_top_posts(count: int = 20, day=None):
    """Fetch the top Product Hunt posts (by votes) for ``day`` (default: yesterday, UK).

    Returns the raw structured ``get_posts`` response. Safe to call from
    synchronous code such as ``send_email.py``.
    """
    return asyncio.run(_fetch(count, day or previous_day()))


def _extract_posts(data):
    """Return the list of post objects from a ``get_posts`` response.

    The MCP server hands back GraphQL connection edges — i.e.
    ``data["data"]["posts"] == [{"node": {...post...}}, ...]`` — so each
    edge's ``node`` is unwrapped to the actual post.
    """
    if isinstance(data, dict):
        inner = data.get("data", data)
        if isinstance(inner, dict) and "posts" in inner:
            data = inner["posts"] or []
    if not isinstance(data, list):
        return []
    return [item.get("node", item) if isinstance(item, dict) else item for item in data]


def posts_for_email(count: int = 20, day=None) -> list[dict]:
    """Return the top posts as ``[{"title", "url", "description"}, ...]`` for the template."""
    items = []
    for post in _extract_posts(fetch_top_posts(count, day)):
        if not isinstance(post, dict):
            continue
        title = post.get("name") or post.get("tagline")
        url = post.get("url") or post.get("website")
        if title and url:
            items.append(
                {
                    "title": title,
                    "url": url,
                    "description": post.get("tagline") or post.get("description") or "",
                }
            )
    return items


if __name__ == "__main__":
    print(f"Top Product Hunt posts for {previous_day()} (UK time, by votes):\n")
    print(json.dumps(fetch_top_posts(), indent=2, default=str))
