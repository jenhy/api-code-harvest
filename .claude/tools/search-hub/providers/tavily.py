"""Tavily MCP connector via stdio transport."""

from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from providers.base import ProviderConnector


class TavilyConnector(ProviderConnector):
    """
    Tavily MCP stdio 连接管理。
    使用 MCP SDK 的 stdio_client 建立子进程通信。
    """

    def __init__(self, command: str, args: list[str], timeout: float = 15):
        self._command = command
        self._args = args
        self._timeout = timeout
        self._session: ClientSession | None = None
        self._stdio_ctx = None
        self._connected = False

    async def connect(self, api_key: str) -> bool:
        """启动 Tavily MCP 子进程并初始化"""
        await self.disconnect()

        try:
            params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env={"TAVILY_API_KEY": api_key},
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
        """获取 Tavily 的所有工具"""
        if not self._session:
            raise RuntimeError("Tavily not connected")
        result = await self._session.list_tools()
        return [t.model_dump() for t in result.tools]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用 Tavily 工具"""
        if not self._session:
            raise RuntimeError("Tavily not connected")
        result = await self._session.call_tool(name, arguments)
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
