"""Request routing with key rotation and provider fallback."""

import asyncio
import copy
import fnmatch
import logging
from typing import Any

from core.key_rotator import KeyRotator
from core.schema_minimizer import minimize_tool_schema
from providers.base import ProviderConnector
from providers import PROVIDER_REGISTRY

logger = logging.getLogger("search-hub")


class ProviderInstance:
    """管理单个供应商的连接和 Key 轮换"""

    def __init__(self, name: str, config: dict, rotator: KeyRotator):
        self.name = name
        self._config = config
        self._rotator = rotator
        self._connector: ProviderConnector | None = None
        self._current_key: str | None = None
        self._tool_prefix = f"{name}_"

        # 创建连接器
        provider_cls = PROVIDER_REGISTRY[name]
        if config.get("transport") == "http":
            self._connector = provider_cls(
                url=config["url"],
                timeout=config.get("timeout", 15),
            )
        else:
            self._connector = provider_cls(
                command=config["command"],
                args=config["args"],
                timeout=config.get("timeout", 15),
            )

    async def connect(self) -> bool:
        """用下一个可用 Key 建立连接"""
        key = self._rotator.next_key(self.name)
        if not key:
            return False
        self._current_key = key
        return await self._connector.connect(key)

    async def discover_tools(self) -> list[dict]:
        """发现本供应商的工具"""
        tools = await self._connector.discover_tools()
        return tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用工具"""
        return await self._connector.call_tool(name, arguments)

    async def disconnect(self):
        """断开连接"""
        await self._connector.disconnect()
        self._current_key = None

    def matches_tool(self, tool_name: str) -> bool:
        """判断工具名是否属于本供应商"""
        return tool_name.startswith(self._tool_prefix)

    async def connect_with_next_key(self) -> bool:
        """切到下一个 Key 并重新连接"""
        await self.disconnect()
        return await self.connect()

    def mark_current_key_failed(self, is_quota_error: bool):
        """标记当前 Key 失败"""
        if self._current_key:
            self._rotator.mark_failed(self.name, self._current_key, is_quota_error)

    def is_available(self) -> bool:
        """检查供应商是否有 Key 可用"""
        return self._rotator.is_provider_available(self.name)

    def key_status(self) -> dict:
        """Key 状态摘要"""
        return self._rotator.key_status(self.name)


class Router:
    """
    路由逻辑：
      1. 根据工具名前缀确定目标供应商
      2. Key 轮换 + 重试
      3. 供应商降级
    """

    def __init__(self, config: dict):
        self._config = config
        rotator = KeyRotator(
            cooldown_seconds=config.get("cooldown_seconds", 60),
            dead_ttl=config.get("dead_key_ttl", 300),
        )

        # 初始化 priority 供应商
        self._priority: list[ProviderInstance] = []
        for name in config.get("provider_priority", []):
            provider_cfg = config["providers"].get(name)
            if provider_cfg:
                rotator.add_keys(name, provider_cfg["api_keys"])
                self._priority.append(ProviderInstance(name, provider_cfg, rotator))

        # 初始化 fallback 供应商
        self._fallback: ProviderInstance | None = None
        fb = config.get("fallback")
        if fb:
            name = fb["provider"]
            provider_cfg = config["providers"].get(name)
            if provider_cfg:
                rotator.add_keys(name, provider_cfg["api_keys"])
                self._fallback = ProviderInstance(name, provider_cfg, rotator)

        self._all_tools: list[dict] = []
        self._initialized = False

    async def initialize(self) -> bool:
        """连接所有供应商并发现工具（并行连接）"""
        all_tools = []

        async def _connect_and_discover(provider: ProviderInstance) -> list[dict]:
            ok = await provider.connect()
            if not ok:
                return []
            try:
                return await provider.discover_tools()
            except Exception as e:
                logger.warning(f"{provider.name} discover failed: {e}")
                provider.mark_current_key_failed(False)
                return []

        # 并行连接所有 priority 供应商
        results = await asyncio.gather(
            *[_connect_and_discover(p) for p in self._priority],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, list):
                all_tools.extend(r)

        # 并行连接 fallback
        if self._fallback:
            fb_tools = await _connect_and_discover(self._fallback)
            all_tools.extend(fb_tools)

        # === Schema 最小化：裁剪冗长描述，减少 token 消耗 ===
        all_tools = self._minimize_tool_schemas(all_tools)

        # === 工具可见性过滤 ===
        all_tools = self._filter_visible_tools(all_tools)

        self._all_tools = all_tools
        self._initialized = True
        return len(all_tools) > 0

    def _minimize_tool_schemas(self, tools: list[dict]) -> list[dict]:
        """对每个工具的 inputSchema 进行最小化处理

        支持三种模式（由 schema_minimization.mode 控制）:
          - standard: 截断 description 到 60 字符，保留约束
          - compact:  截断到 30 字符，移除约束/default (推荐)
          - minimal:  仅保留顶层 description，最大节省
        """
        cfg = self._config.get("schema_minimization", {})
        mode = cfg.get("mode", "compact")

        if mode == "standard":
            minimized = [minimize_tool_schema(t["inputSchema"], max_desc=60, strip_nested_descriptions=False, keep_constraints=True) if "inputSchema" in t else t for t in tools]
        elif mode == "minimal":
            minimized = [minimize_tool_schema(t["inputSchema"], max_desc=30, strip_nested_descriptions=True, keep_constraints=False) if "inputSchema" in t else t for t in tools]
        else:  # compact (default)
            minimized = [minimize_tool_schema(t["inputSchema"], max_desc=30, strip_nested_descriptions=False, keep_constraints=False) if "inputSchema" in t else t for t in tools]

        # Preserve tool name/description (top-level) while swapping inputSchema
        result = []
        for orig, new_schema in zip(tools, minimized):
            tool = dict(orig)
            tool["inputSchema"] = new_schema
            result.append(tool)

        logger.info(f"Schema minimization applied (mode={mode}) for {len(result)} tools")
        return result

    def _filter_visible_tools(self, tools: list[dict]) -> list[dict]:
        """根据配置过滤工具可见性"""
        visibility = self._config.get("tool_visibility", {})
        if visibility.get("mode") == "all":
            # mode=all = 暴露所有工具（仅应用 schema 最小化）
            pass

        # 处理 exclude 列表（glob 模式）
        excludes = visibility.get("exclude", [])
        if not excludes:
            return tools

        filtered = []
        for tool in tools:
            name = tool.get("name", "")
            if any(fnmatch.fnmatch(name, pattern) for pattern in excludes):
                logger.debug(f"Hiding tool: {name}")
                continue
            filtered.append(tool)

        hidden = len(tools) - len(filtered)
        if hidden:
            logger.info(f"Hidden {hidden} tools via visibility filter")
        return filtered

    def get_all_tools(self) -> list[dict]:
        """返回合并后的全量工具列表"""
        return copy.deepcopy(self._all_tools)

    async def route(self, tool_name: str, arguments: dict) -> dict:
        """路由工具调用（含 Key 轮换重试和供应商降级）"""
        if not self._initialized:
            raise RuntimeError("Search Hub not initialized")

        # 先匹配 priority 供应商
        for provider in self._priority:
            if provider.matches_tool(tool_name):
                return await self._try_provider(provider, tool_name, arguments)

        # 再匹配 fallback
        if self._fallback and self._fallback.matches_tool(tool_name):
            return await self._try_provider(self._fallback, tool_name, arguments)

        raise RuntimeError(f"Unknown tool: {tool_name}")

    async def _try_provider(
        self, provider: ProviderInstance, tool_name: str, arguments: dict
    ) -> dict:
        """带 Key 轮换重试的调用"""
        max_retries = 3

        for attempt in range(max_retries):
            if not provider.is_available():
                break

            if attempt > 0:
                ok = await provider.connect_with_next_key()
                if not ok:
                    continue

            try:
                return await provider.call_tool(tool_name, arguments)
            except Exception as e:
                err_str = str(e).lower()
                is_quota = any(code in err_str for code in ["402", "403", "429", "quota", "rate limit"])
                provider.mark_current_key_failed(is_quota)

                if attempt < max_retries - 1:
                    logger.warning(
                        f"{provider.name} failed (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                else:
                    logger.error(
                        f"{provider.name} exhausted after {max_retries} attempts: {e}"
                    )

        # 如果当前是 priority，尝试降级到 fallback
        if provider in self._priority and self._fallback and self._fallback.matches_tool(tool_name):
            logger.info(f"Falling back to {self._fallback.name} for {tool_name}")
            return await self._try_provider(self._fallback, tool_name, arguments)

        raise RuntimeError(f"All keys exhausted for {tool_name}")

    async def disconnect_all(self):
        """断开所有连接"""
        for provider in self._priority:
            await provider.disconnect()
        if self._fallback:
            await self._fallback.disconnect()

    def get_diagnosis(self) -> list[dict]:
        """返回诊断信息，用于 doctor 工具"""
        result = []
        for provider in self._priority:
            result.append({
                "provider": provider.name,
                "available": provider.is_available(),
                "keys": provider.key_status(),
            })
        if self._fallback:
            result.append({
                "provider": f"{self._fallback.name} (fallback)",
                "available": self._fallback.is_available(),
                "keys": self._fallback.key_status(),
            })
        return result
