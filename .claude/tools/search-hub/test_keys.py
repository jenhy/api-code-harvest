"""测试所有 API Key 的连通性，每个 Key 至少执行一次查询。"""
import asyncio
import sys
import time

sys.path.insert(0, ".")

from providers.firecrawl import FirecrawlConnector
from providers.tavily import TavilyConnector

FIRECRAWL_KEYS = [
    "fc-436ef7daa9e64c0ab13f4dfe6503ca96",
    "fc-b76cd38832a54dae856bd5245ed41298",
    "fc-f87a13ca805b403d9de81400d9144e66",
    "fc-4f5ef3fef37b4f01a73270a367072769",
]

TAVILY_KEYS = [
    "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",
    "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",
    "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",
    "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",
    "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",
    "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",
]

FC_CMD = ["node", "C:\\Users\\Jenhy\\.claude\\tools\\search-hub\\node_modules\\firecrawl-mcp\\dist\\index.js"]
TV_CMD = ["node", "C:\\Users\\Jenhy\\.claude\\tools\\search-hub\\node_modules\\tavily-mcp\\build\\index.js"]


async def test_firecrawl_key(key: str, index: int) -> dict:
    """测试单个 Firecrawl Key"""
    connector = FirecrawlConnector(FC_CMD[0], FC_CMD[1:], timeout=15)
    result = {"index": index + 1, "key": key[:15] + "...", "connect": False, "search": False, "error": "", "time": 0}

    try:
        ok = await connector.connect(key)
        if not ok:
            result["error"] = "connect failed"
            return result
        result["connect"] = True

        t0 = time.perf_counter()
        resp = await connector.call_tool("firecrawl_search", {"query": "AI testing 2026", "limit": 2})
        elapsed = round(time.perf_counter() - t0, 2)
        result["time"] = elapsed
        content = resp.get("content", [])
        text = next((c.get("text", "") for c in content if c.get("type") == "text"), "")
        if text and '"success": true' in text:
            result["search"] = True
        else:
            result["error"] = f"unexpected: {text[:60]}"
    except Exception as e:
        result["error"] = str(e)[:80]
    finally:
        await connector.disconnect()

    return result


async def test_tavily_key(key: str, index: int) -> dict:
    """测试单个 Tavily Key"""
    connector = TavilyConnector(TV_CMD[0], TV_CMD[1:], timeout=15)
    result = {"index": index + 1, "key": key[:15] + "...", "connect": False, "search": False, "error": "", "time": 0}

    try:
        ok = await connector.connect(key)
        if not ok:
            result["error"] = "connect failed"
            return result
        result["connect"] = True

        t0 = time.perf_counter()
        resp = await connector.call_tool("tavily-search", {"query": "AI testing 2026", "max_results": 2})
        elapsed = round(time.perf_counter() - t0, 2)
        result["time"] = elapsed
        content = resp.get("content", [])
        result["search"] = len(content) > 0
        if not result["search"]:
            result["error"] = "empty response"
    except Exception as e:
        result["error"] = str(e)[:80]
    finally:
        await connector.disconnect()

    return result


def print_results(provider: str, results: list[dict]):
    print(f"\n{'='*60}")
    print(f"  {provider} ({len(results)} keys)")
    print(f"{'='*60}")
    print(f"  {'#':>2} | {'Key':<18} | {'Connect':>7} | {'Search':>6} | {'Time':>6} | {'Error'}")
    print(f"  {'-'*58}")
    for r in results:
        ok = "OK" if r["connect"] else "FAIL"
        sg = "OK" if r["search"] else "FAIL"
        err = r["error"] if r["error"] else "-"
        print(f"  {r['index']:>2} | {r['key']:<18} | {ok:>7} | {sg:>6} | {r['time']:>5}s | {err}")


async def main():
    fc_results = []
    for i, key in enumerate(FIRECRAWL_KEYS):
        sys.stdout.write(f"FC #{i+1}/{len(FIRECRAWL_KEYS)}... ")
        sys.stdout.flush()
        r = await test_firecrawl_key(key, i)
        status = "OK" if r["search"] else f"FAIL ({r['error']})"
        print(f"{r['time']}s {status}")
        fc_results.append(r)

    tv_results = []
    for i, key in enumerate(TAVILY_KEYS):
        sys.stdout.write(f"TV #{i+1}/{len(TAVILY_KEYS)}... ")
        sys.stdout.flush()
        r = await test_tavily_key(key, i)
        status = "OK" if r["search"] else f"FAIL ({r['error']})"
        print(f"{r['time']}s {status}")
        tv_results.append(r)

    print_results("Firecrawl", fc_results)
    print_results("Tavily", tv_results)

    fc_ok = sum(1 for r in fc_results if r["search"])
    tv_ok = sum(1 for r in tv_results if r["search"])
    print(f"\n{'='*60}")
    print(f"  总计: Firecrawl {fc_ok}/{len(fc_results)} 可用, Tavily {tv_ok}/{len(tv_results)} 可用")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
