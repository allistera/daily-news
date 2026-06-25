import asyncio
import json
import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

env = os.environ
from fastmcp import Client

client = Client({
    "mcpServers": {
        "product-hunt": {
            "command": "product-hunt-mcp",
            "env": {"PRODUCT_HUNT_TOKEN": env["PRODUCT_HUNT_TOKEN"]},
        }
    }
})

# Build the previous day's window in UK time (Europe/London handles BST/GMT),
# converted to UTC for the API.
UK = ZoneInfo("Europe/London")
today = datetime.now(UK).date()
yesterday = today - timedelta(days=1)
day_start = datetime.combine(yesterday, time.min, tzinfo=UK)
day_end = datetime.combine(today, time.min, tzinfo=UK)
posted_after = day_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
posted_before = day_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def main():
    async with client:
        result = await client.call_tool(
            "get_posts",
            {
                "order": "VOTES",
                "posted_after": posted_after,
                "posted_before": posted_before,
                "count": 20,  # max allowed
            },
        )
        # Prefer the deserialized structured data; fall back to raw text content.
        if result.data is not None:
            return result.data
        return [getattr(block, "text", str(block)) for block in result.content]


print(f"Top Product Hunt posts for {yesterday} (UK time, by votes):\n")
results = asyncio.run(main())
print(json.dumps(results, indent=2, default=str))
