"""Orchestrator 单元测试 — 覆盖 CLI、GmailApi 集成、_make_alias"""
import argparse
import asyncio
import tempfile
from dataclasses import asdict

import pytest
import yaml

from src.config import Settings


class TestMakeAlias:
    """验证 Gmail + aliasing 生成逻辑"""

    def test_basic_alias(self):
        """ross.chen85.dev@gmail.com → ross.chen85.dev+hvoy001@gmail.com"""
        user, domain = "ross.chen85.dev@gmail.com".split("@")
        alias = f"{user}+hvoy{1:03d}@{domain}"
        assert alias == "ross.chen85.dev+hvoy001@gmail.com"

    def test_counter_010(self):
        user, domain = "test@gmail.com".split("@")
        alias = f"{user}+hvoy{10:03d}@{domain}"
        assert alias == "test+hvoy010@gmail.com"

    def test_counter_337(self):
        user, domain = "test@gmail.com".split("@")
        alias = f"{user}+hvoy{337:03d}@{domain}"
        assert alias == "test+hvoy337@gmail.com"


class TestCLIArgs:
    """验证 CLI 参数变更"""

    def test_new_args_present(self):
        """验证 --proxy 和 --email 存在，--gmail 和 --app-password 消失"""
        from src.main import main as main_func

        # 通过 argparse 解析测试
        import inspect
        source = inspect.getsource(main_func)
        assert "--proxy" in source, "需要 --proxy CLI 参数"
        assert "--email" in source, "需要 --email CLI 参数"
        assert "--gmail" not in source, "--gmail 应已移除"
        assert "--app-password" not in source, "--app-password 应已移除"
        assert "--phase" not in source, "--phase 应已移除"

    def test_default_count(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int, default=1)
        args = parser.parse_args([])
        assert args.count == 1


class TestConfigOverride:
    """验证 CLI 参数覆盖配置"""

    def test_proxy_override(self):
        """--proxy 10.0.0.1:8888 覆盖 config.yaml 的 proxy_host/proxy_port"""
        config_data = {
            "gmail": {
                "proxy_host": "127.0.0.1",
                "proxy_port": 22222,
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                          delete=False, encoding="utf-8") as f:
            yaml.dump(config_data, f)
            config_path = f.name

        settings = Settings.from_yaml(config_path)

        # 模拟 CLI 覆盖
        proxy_arg = "10.0.0.1:8888"
        host, _, port = proxy_arg.partition(":")
        settings.gmail.proxy_host = host
        if port:
            settings.gmail.proxy_port = int(port)

        assert settings.gmail.proxy_host == "10.0.0.1"
        assert settings.gmail.proxy_port == 8888

    def test_email_override(self):
        """--email 覆盖 config.yaml 的 email_address"""
        config_data = {
            "gmail": {
                "email_address": "ross.chen85.dev@gmail.com",
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                          delete=False, encoding="utf-8") as f:
            yaml.dump(config_data, f)
            config_path = f.name

        settings = Settings.from_yaml(config_path)
        settings.gmail.email_address = "override@gmail.com"
        assert settings.gmail.email_address == "override@gmail.com"


class TestChromePath:
    """验证 Chrome 启动路径修复"""

    def test_chrome_path_defined(self):
        """验证 CHROME_PATH 常量指向正确路径"""
        from src.main import CHROME_PATH
        assert "chrome.exe" in CHROME_PATH.lower()
        assert "Program Files" in CHROME_PATH

    def test_no_channel_param(self):
        """验证 main.py 不再使用 channel='chrome'"""
        import inspect
        from src.main import Orchestrator
        source = inspect.getsource(Orchestrator.run)
        assert "channel" not in source, "不应再使用 channel='chrome'，应使用 executable_path"
        assert "executable_path" in source, "应使用 executable_path"


class TestOrchestratorInstance:
    """验证 Orchestrator 实例化包含 GmailApi"""

    def test_orchestrator_has_gmail(self):
        """验证 Orchestrator 创建 GmailApi 实例"""
        from src.main import Orchestrator
        settings = Settings()
        settings.gmail.email_address = "test@gmail.com"
        orch = Orchestrator(settings)
        assert hasattr(orch, "gmail")

    def test_orchestrator_make_alias(self):
        """验证 _make_alias 生成正确别名"""
        from src.main import Orchestrator
        settings = Settings()
        settings.gmail.email_address = "ross.chen85.dev@gmail.com"
        orch = Orchestrator(settings)
        alias = orch._make_alias(1)
        assert alias == "ross.chen85.dev+hvoy001@gmail.com"
        alias_337 = orch._make_alias(337)
        assert alias_337 == "ross.chen85.dev+hvoy337@gmail.com"


class TestVerificationFlow:
    """验证验证链接打开后点击"去登录"按钮"""

    def test_go_login_click_present_in_run_full(self):
        """验证 _run_full 中打开验证链接后有点击"去登录"逻辑"""
        import inspect
        from src.main import Orchestrator
        source = inspect.getsource(Orchestrator._run_full)
        assert 'has-text("去登录")' in source, "应有点击'去登录'的逻辑"

    def test_go_login_click_present_in_run_one_cycle(self):
        """验证 _run_one_cycle 中打开验证链接后有点击"去登录"逻辑"""
        import inspect
        from src.main import Orchestrator
        source = inspect.getsource(Orchestrator._run_one_cycle)
        assert 'has-text("去登录")' in source, "应有点击'去登录'的逻辑"
