"""Firecrawl MCP connector via stdio transport.

Firecrawl MCP runs as a local npx process (firecrawl-mcp),
with the API key passed via environment variable FIRECRAWL_API_KEY.
"""

from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from providers.base import ProviderConnector


class FirecrawlConnector(ProviderConnector):
    """
    Firecrawl MCP stdio 连接管理。
    使用 MCP SDK 的 stdio_client 启动 firecrawl-mcp 子进程。
    """

    def __init__(self, command: str, args: list[str], timeout: float = 60):
        self._command = command
        self._args = args
        self._timeout = timeout
        self._session: ClientSession | None = None
        self._stdio_ctx = None
        self._connected = False

    async def connect(self, api_key: str) -> bool:
        """启动 Firecrawl MCP 子进程并初始化"""
        await self.disconnect()

        try:
            params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env={
                    "FIRECRAWL_API_KEY": api_key,
                    # 防止父进程代理设置干扰子进程的 Firecrawl API 直连
                    "NO_PROXY": "localhost,127.0.0.1,firecrawl.dev,api.firecrawl.dev,mcp.firecrawl.dev",
                },
            )
            ctx = stdio_client(params)
            self._stdio_ctx = ctx
            read, write = await ctx.__aenter__()

            self._session = ClientSession(read, write)
            await self._session.__aenter__()
            await self._session.initialize()

            self._connected = True
            return True

        except Exception:
            await self.disconnect()
            return False

    async def discover_tools(self) -> list[dict[str, Any]]:
        """获取 Firecrawl 的所有工具"""
        if not self._session:
            raise RuntimeError("Firecrawl not connected")
        result = await self._session.list_tools()
        return [t.model_dump() for t in result.tools]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用 Firecrawl 工具"""
        if not self._session:
            raise RuntimeError("Firecrawl not connected")

        result = await self._session.call_tool(name, arguments)

        # MCP SDK 将 tool error（如 402）返回为 CallToolResult.isError=True，
        # 而非抛出异常。但 _try_provider 的重试机制依赖异常触发。
        # 检查结果中是否包含错误，如有则抛出异常让重试机制生效。
        if result.isError:
            parts = []
            for c in result.content:
                if hasattr(c, "text") and c.text:
                    parts.append(c.text)
                elif hasattr(c, "data"):
                    # ImageContent：记录 MIME 类型而非 base64 数据
                    mime = getattr(c, "mimeType", "unknown")
                    parts.append(f"[Image: {mime}]")
                elif hasattr(c, "resource"):
                    # EmbeddedResource：记录资源类型
                    parts.append(f"[Resource: {getattr(c, 'resource', {})}]")
            error_text = " ".join(parts)

            # NOTE: error_text 来自 Firecrawl MCP 的错误响应正文，
            # 将被记录到日志/异常追踪系统。确认不包含敏感信息后再上线。
            # 若 arguments 可能含敏感字段，考虑脱敏处理。
            if not error_text:
                error_text = f"Tool '{name}' failed (arguments={arguments})"
            raise RuntimeError(error_text)

        return {"content": [c.model_dump() for c in result.content]}

    async def disconnect(self):
        """终止子进程"""
        self._connected = False
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
        if self._stdio_ctx:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._stdio_ctx = None

    async def health(self) -> bool:
        """检查连接是否正常"""
        if not self._connected or not self._session:
            return False
        try:
            await self._session.send_ping()
            return True
        except Exception:
            return False
