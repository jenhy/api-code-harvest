"""Search Hub MCP Server — passthrough proxy with key rotation."""

import json
import logging
import os
import sys

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

from core.router import Router

logging.basicConfig(
    level=logging.WARNING,
    format="%(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("search-hub")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config(path: str | None = None) -> dict:
    if path is None:
        path = os.path.join(BASE_DIR, "config.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main():
    config = load_config()
    router = Router(config)

    logger.info("Initializing providers...")
    ok = await router.initialize()
    if not ok:
        logger.error("No tools discovered from any provider. Exiting.")
        sys.exit(1)

    tools = router.get_all_tools()
    logger.info(f"Discovered {len(tools)} tools total")

    app = Server("search-hub")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        mcp_tools = []
        for t in tools:
            mcp_tools.append(Tool(
                name=t["name"],
                description=t.get("description", ""),
                inputSchema=t.get("inputSchema", {"type": "object", "properties": {}}),
            ))
        return mcp_tools

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        # 特殊工具: doctor — 直接在 Search Hub 内部处理
        if name == "doctor":
            return await _handle_doctor(router)

        try:
            result = await router.route(name, arguments)
            content = result.get("content", [])
            text_parts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    text_parts.append(c["text"])
                elif isinstance(c, str):
                    text_parts.append(c)
            return [TextContent(type="text", text="\n".join(text_parts) or "OK")]
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


async def _handle_doctor(router: Router) -> list[TextContent]:
    """诊断所有供应商状态"""
    diagnosis = router.get_diagnosis()
    lines = ["Search Hub Diagnosis", "====================", ""]
    for entry in diagnosis:
        status = "AVAILABLE" if entry["available"] else "UNAVAILABLE"
        lines.append(f"[{status}] {entry['provider']}")
        for key, info in entry["keys"].items():
            lines.append(f"  {key}: failures={info['failures']}, status={info['status']}")
        lines.append("")
    return [TextContent(type="text", text="\n".join(lines))]


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
