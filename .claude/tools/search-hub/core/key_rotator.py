"""Key pool management, rotation, and cooldown."""

import time
from collections import defaultdict


class KeyRotator:
    """
    Key 池管理:
      - 每个供应商拥有独立的 Key 列表
      - 轮换策略: round_robin（v1 唯一策略）
      - 错误计数: 跟踪每个 Key 的状态
      - 键冷却: 临时错误冷却 cooldown_seconds 秒后可重试
      - 死键 TTL: 402/403/429 标记为 dead，但 dead_ttl 秒后自动恢复
    """

    def __init__(self, cooldown_seconds: int = 60, dead_ttl: int = 300):
        self.cooldown_seconds = cooldown_seconds
        self.dead_ttl = dead_ttl  # 死键 5 分钟后自动恢复
        # provider -> list of keys
        self._keys: dict[str, list[str]] = defaultdict(list)
        # provider -> current index
        self._indices: dict[str, int] = defaultdict(int)
        # key -> failure count
        self._failures: dict[str, int] = defaultdict(int)
        # key -> timestamp when it can be retried (0 = available)
        self._cooldowns: dict[str, float] = {}
        # key -> True if permanently dead (quota error)
        self._dead: dict[str, bool] = defaultdict(bool)
        # key -> timestamp when dead was set (for auto-recovery)
        self._dead_since: dict[str, float] = {}

    def add_keys(self, provider: str, keys: list[str]):
        """注册供应商的 Key 列表"""
        self._keys[provider] = keys.copy()
        self._indices[provider] = 0

    def next_key(self, provider: str) -> str | None:
        """取下一个可用 Key（round-robin），无可用 Key 时返回 None"""
        now = time.time()
        keys = self._keys.get(provider, [])
        if not keys:
            return None

        # 从当前索引开始，循环查找可用 Key
        n = len(keys)
        for _ in range(n):
            idx = self._indices[provider]
            key = keys[idx]
            self._indices[provider] = (idx + 1) % n

            if self._dead.get(key):
                # 死键在 dead_ttl 秒后自动恢复
                dead_since = self._dead_since.get(key, 0)
                if dead_since and (now - dead_since) > self.dead_ttl:
                    self._dead[key] = False
                    self._dead_since.pop(key, None)
                    self._cooldowns[key] = now + min(30, self.cooldown_seconds)
                else:
                    continue
            cooldown = self._cooldowns.get(key, 0)
            if cooldown > now:
                continue
            return key

        return None

    def mark_failed(self, provider: str, key: str, is_quota_error: bool):
        """标记 Key 失败"""
        self._failures[key] += 1

        if is_quota_error:
            # 429/402/403 → 标记不可用（dead_ttl 秒后自动恢复）
            self._dead[key] = True
            self._dead_since.setdefault(key, time.time())
        else:
            # 临时错误 → 冷却 cooldown_seconds 秒
            self._cooldowns[key] = time.time() + self.cooldown_seconds

    def is_provider_available(self, provider: str) -> bool:
        """检查供应商是否还有可用 Key（死键在 dead_ttl 后自动恢复）"""
        return self.next_key(provider) is not None

    def reset_provider(self, provider: str):
        """重置供应商所有 Key 状态（手动恢复用）"""
        for key in self._keys.get(provider, []):
            self._dead[key] = False
            self._cooldowns.pop(key, None)
        self._indices[provider] = 0

    def key_status(self, provider: str) -> dict:
        """返回供应商 Key 状态摘要，用于 doctor 诊断"""
        now = time.time()
        result = {}
        for key in self._keys.get(provider, []):
            remaining = None
            if self._dead.get(key):
                dead_since = self._dead_since.get(key, 0)
                if dead_since:
                    remaining = max(0, int(self.dead_ttl - (now - dead_since)))
                status = f"dead (recovery in {remaining}s)" if remaining else "dead"
            elif self._cooldowns.get(key, 0) > now:
                ttl = int(self._cooldowns[key] - now)
                status = f"cooldown ({ttl}s)"
            else:
                status = "active"
            result[key[:12] + "..."] = {
                "failures": self._failures.get(key, 0),
                "status": status,
            }
        return result
