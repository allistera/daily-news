import asyncio
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

async def list_actions():
    async with client:
        return await client.list_tools()


tools = asyncio.run(list_actions())

print(f"{len(tools)} actions available (* = required param):\n")
for tool in tools:
    print(f"- {tool.name}")
    if tool.description:
        print(f"    {tool.description.strip().splitlines()[0]}")
    schema = tool.inputSchema or {}
    params = schema.get("properties", {})
    if params:
        required = set(schema.get("required", []))
        rendered = ", ".join(
            f"{name}{'*' if name in required else ''}" for name in params
        )
        print(f"    params: {rendered}")
    print()
