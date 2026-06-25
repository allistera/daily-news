import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

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

# Build the previous day's UTC window: [yesterday 00:00, today 00:00).
today = datetime.now(timezone.utc).date()
yesterday = today - timedelta(days=1)
posted_after = f"{yesterday}T00:00:00Z"
posted_before = f"{today}T00:00:00Z"


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


print(f"Top Product Hunt posts for {yesterday} (by votes):\n")
results = asyncio.run(main())
print(json.dumps(results, indent=2, default=str))
