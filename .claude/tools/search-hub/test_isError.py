"""TDD: Verify FirecrawlConnector.call_tool raises on MCP error.

RED:   Old code returns error as content (no exception) -- test FAILS
GREEN: Fixed code checks isError and raises RuntimeError -- test PASSES
"""
import asyncio
import sys

sys.path.insert(0, ".")

from providers.firecrawl import FirecrawlConnector

BAD_KEY = "fc-065fb635c6d44d2fbde41051bd4dd0eb"       # Key 0 -- 402 on MCP
GOOD_KEY = "fc-436ef7daa9e64c0ab13f4dfe6503ca96"      # Key 1 -- works
FC_ARGS = [r"C:\Users\Jenhy\.claude\tools\search-hub\node_modules\firecrawl-mcp\dist\index.js"]


async def test_raises_on_mcp_error():
    """call_tool should raise RuntimeError when firecrawl-mcp returns 402."""
    connector = FirecrawlConnector("node", FC_ARGS, timeout=15)
    try:
        ok = await connector.connect(BAD_KEY)
        assert ok, "connect failed"
        await connector.call_tool("firecrawl_search", {"query": "test", "limit": 1})
        # If we got here, no exception was thrown -- BUG
        await connector.disconnect()
        raise AssertionError("Expected RuntimeError, but none was raised")
    except RuntimeError:
        pass  # Expected -- fix works
    finally:
        await connector.disconnect()


async def test_good_key_still_works():
    """Regression: good key still returns search results."""
    connector = FirecrawlConnector("node", FC_ARGS, timeout=15)
    try:
        ok = await connector.connect(GOOD_KEY)
        assert ok, "connect failed"
        result = await connector.call_tool("firecrawl_search", {"query": "test", "limit": 1})
        content = result.get("content", [])
        assert content, "empty response"
        text = content[0].get("text", "") if isinstance(content[0], dict) else ""
        assert '"success": true' in text, f"unexpected: {text[:80]}"
    except RuntimeError as e:
        raise AssertionError(f"good key should not raise: {e}")
    finally:
        await connector.disconnect()


async def main():
    results = []
    for name, coro in [
        ("MCP error -> RuntimeError", test_raises_on_mcp_error()),
        ("Good key regression", test_good_key_still_works()),
    ]:
        try:
            await coro
            results.append((name, "PASS"))
            print(f"  PASS  {name}")
        except (AssertionError, Exception) as e:
            results.append((name, "FAIL"))
            print(f"  FAIL  {name}: {e}")

    print()
    passed = sum(1 for _, s in results if s == "PASS")
    total = len(results)
    print(f"  {passed}/{total} tests passed")

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
