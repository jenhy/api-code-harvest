"""Abstract base class for provider MCP connectors."""

from abc import ABC, abstractmethod
from typing import Any


class ProviderConnector(ABC):
    """供应商 MCP 连接管理器"""

    @abstractmethod
    async def connect(self, api_key: str) -> bool:
        """用指定 Key 建立 MCP 连接"""

    @abstractmethod
    async def discover_tools(self) -> list[dict[str, Any]]:
        """调用 tools/list 发现所有工具，返回 Tool dict 列表"""

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """转发工具调用请求，返回 CallToolResult dict"""

    @abstractmethod
    async def disconnect(self):
        """断开当前 MCP 连接"""

    @abstractmethod
    async def health(self) -> bool:
        """检查连接是否正常"""
