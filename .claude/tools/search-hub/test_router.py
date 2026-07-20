"""Directly test search-hub Router with the actual config."""
import asyncio, sys, json, os
sys.path.insert(0, ".")
os.chdir(".")

from core.router import Router
import yaml


async def main():
    # Load the actual config
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print("=== Config check ===")
    print(f"Priority: {config.get('provider_priority')}")
    fc_cfg = config["providers"]["firecrawl"]
    print(f"Firecrawl keys ({len(fc_cfg['api_keys'])}):")
    for i, k in enumerate(fc_cfg["api_keys"]):
        print(f"  Key {i}: {k[:15]}...")
    print(f"Fallback: {config.get('fallback')}")

    # Create the router
    router = Router(config)
    print("\n=== Initializing router ===")
    ok = await router.initialize()
    print(f"Initialize OK: {ok}")
    print(f"Tools discovered: {len(router.get_all_tools())}")

    if ok:
        # Diagnose key status
        print("\n=== Provider diagnosis ===")
        diag = router.get_diagnosis()
        for entry in diag:
            print(f"[{entry['provider']}] available={entry['available']}")
            for key, info in entry["keys"].items():
                print(f"  {key}: {info}")

        # Try calling firecrawl_search
        print("\n=== Calling firecrawl_search ===")
        try:
            result = await router.route("firecrawl_search", {"query": "test", "limit": 1})
            content = result.get("content", [])
            for c in content:
                if isinstance(c, dict):
                    print(f"  Content: {str(c.get('text', ''))[:300]}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

    await router.disconnect_all()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
