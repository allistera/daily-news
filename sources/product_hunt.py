import asyncio
import json
import os

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

async def main():
    async with client:
        tools = await client.list_tools()
        print("Available tools:", [t.name for t in tools])
        result = await client.call_tool("get_posts", {"count": 5})
        # Prefer the deserialized structured data; fall back to raw text content.
        if result.data is not None:
            return result.data
        return [getattr(block, "text", str(block)) for block in result.content]


results = asyncio.run(main())
print(json.dumps(results, indent=2, default=str))
