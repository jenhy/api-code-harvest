"""Exact reproduction: search-hub's env + subprocess flow"""
import asyncio, os, json

# Set proxy exactly as settings.json does
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:22222'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:22222'

async def main():
    from mcp.client.stdio import StdioServerParameters, stdio_client, get_default_environment
    from mcp.client.session import ClientSession

    # 1. Show what env the subprocess actually gets
    default_env = get_default_environment()
    merged_env = {**default_env, 'FIRECRAWL_API_KEY': 'fc-f87a13ca805b403d9de81400d9144e66'}

    print('=== Proxy vars in merged env ===')
    proxy_vars = [k for k in merged_env if 'proxy' in k.lower()]
    if proxy_vars:
        for k in sorted(proxy_vars):
            print(f'  {k}={merged_env[k]}')
    else:
        print('  (none found)')
    print(f'  Has FIRECRAWL_API_KEY: {"FIRECRAWL_API_KEY" in merged_env}')
    print(f'  Env dict size: {len(merged_env)} vars')

    # 2. Connect and search exactly like search-hub does
    params = StdioServerParameters(
        command='node',
        args=['C:\\Users\\Jenhy\\.claude\\tools\\search-hub\\node_modules\\firecrawl-mcp\\dist\\index.js'],
        env={'FIRECRAWL_API_KEY': 'fc-f87a13ca805b403d9de81400d9144e66'},
    )

    ctx = stdio_client(params)
    read, write = await ctx.__aenter__()
    session = ClientSession(read, write)
    await session.__aenter__()
    await session.initialize()

    result = await session.call_tool('firecrawl_search', {'query': 'test', 'limit': 1})
    for c in result.content:
        if c.type == 'text':
            data = json.loads(c.text)
            print(f'\n=== Search result ===')
            print(f'  success: {data.get("success")}')
            print(f'  results count: {len(data.get("data", {}).get("web", []))}')

    await session.__aexit__(None, None, None)
    await ctx.__aexit__(None, None, None)

asyncio.run(main())
