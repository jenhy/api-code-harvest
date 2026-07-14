"""配置管理测试 — 验证 config.yaml 格式正确 + GmailConfig"""
import os
import tempfile

import pytest
import yaml

from src.config import GmailConfig, Settings


class TestGmailConfig:
    """纯逻辑：验证 dataclass 默认值和字段覆盖。"""

    def test_default_values(self):
        cfg = GmailConfig()
        assert cfg.credentials_file == "credentials.json"
        assert cfg.token_pickle == "token.pickle"
        assert cfg.email_address == ""
        assert cfg.proxy_host == "127.0.0.1"
        assert cfg.proxy_port == 22222

    def test_custom_values(self):
        cfg = GmailConfig(
            credentials_file="my_creds.json",
            token_pickle="my_token.pickle",
            email_address="test@gmail.com",
            proxy_host="10.0.0.1",
            proxy_port=8888,
        )
        assert cfg.credentials_file == "my_creds.json"
        assert cfg.token_pickle == "my_token.pickle"
        assert cfg.email_address == "test@gmail.com"
        assert cfg.proxy_host == "10.0.0.1"
        assert cfg.proxy_port == 8888

    def test_from_yaml_with_gmail(self):
        """读取包含 gmail 节的 YAML，验证字段正确映射。"""
        data = {
            "browser": {"headless": True},
            "gmail": {
                "credentials_file": "creds/custom.json",
                "token_pickle": "creds/token.pickle",
                "email_address": "ross.chen85.dev@gmail.com",
                "proxy_host": "127.0.0.1",
                "proxy_port": 22222,
            },
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(data, f)
            tmp_path = f.name
        try:
            settings = Settings.from_yaml(tmp_path)
            assert settings.browser.headless is True
            assert settings.gmail.email_address == "ross.chen85.dev@gmail.com"
            assert settings.gmail.proxy_host == "127.0.0.1"
            assert settings.gmail.proxy_port == 22222
            assert settings.gmail.credentials_file == "creds/custom.json"
        finally:
            os.unlink(tmp_path)

    def test_from_yaml_without_gmail(self):
        """没有 gmail 节时使用默认值。"""
        data = {"browser": {"headless": False}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(data, f)
            tmp_path = f.name
        try:
            settings = Settings.from_yaml(tmp_path)
            assert isinstance(settings.gmail, GmailConfig)
            assert settings.gmail.email_address == ""
            assert settings.gmail.proxy_host == "127.0.0.1"
            assert settings.gmail.proxy_port == 22222
        finally:
            os.unlink(tmp_path)


class TestSettings:
    def test_load_from_real_config_yaml(self):
        s = Settings.from_yaml("config.yaml")
        assert s.batch.count == 1
        assert s.browser.headless is False
        assert s.browser.viewport_width == 1280
        assert s.timeouts.email_verification == 300
        assert s.retry.mail_api_retries == 3
        assert s.mode.flow == "sequential"

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            Settings.from_yaml("nonexistent.yaml")

    def test_empty_yaml_uses_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{}")
            f.flush()
            s = Settings.from_yaml(f.name)
        assert s.batch.count == 1
        assert s.browser.headless is False
        os.unlink(f.name)

    def test_partial_override_keeps_other_defaults(self):
        yaml_content = """
batch:
  count: 10
browser:
  headless: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            s = Settings.from_yaml(f.name)
        assert s.batch.count == 10
        assert s.browser.headless is True
        assert s.browser.viewport_width == 1280  # 未覆盖的保持默认值
        assert s.timeouts.email_verification == 300
        os.unlink(f.name)
