"""Quick test: does StdioServerParameters pass env correctly?"""
import asyncio, os

async def main():
    api_key = "fc-f87a13ca805b403d9de81400d9144e66"

    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command="node",
        args=["C:\\Users\\Jenhy\\.claude\\tools\\search-hub\\node_modules\\firecrawl-mcp\\dist\\index.js"],
        env={"FIRECRAWL_API_KEY": api_key},
    )

    ctx = stdio_client(params)
    read, write = await ctx.__aenter__()

    from mcp.client.session import ClientSession
    session = ClientSession(read, write)
    await session.__aenter__()
    await session.initialize()

    # Check env vars inside subprocess
    result = await session.call_tool("firecrawl_search", {"query": "hello world", "limit": 1})
    for c in result.content:
        if c.type == "text":
            print("SEARCH:", c.text[:200])

    await session.__aexit__(None, None, None)
    await ctx.__aexit__(None, None, None)

asyncio.run(main())
