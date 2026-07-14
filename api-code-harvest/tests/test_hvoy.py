"""HvoyRegistrar 测试 — E2E 验证 + 单元测试

⚠️ E2E 测试需要真实 Chrome Profile + 有头浏览器，手动确认。
"""
from dataclasses import asdict

import pytest

from src.models import AccountInfo, InviteCode, RegistrationResult
from src.sites.hvoy import HvoyRegistrar


# ====================================================================
# 单元测试 — 类方法和数据模型验证（无需浏览器）
# ====================================================================

class TestHvoyRegistrarInstance:
    """验证 HvoyRegistrar 实例化正确且包含新增方法"""

    def test_importable(self):
        registrar = HvoyRegistrar()
        assert isinstance(registrar, HvoyRegistrar)

    def test_has_new_methods(self):
        """验证新增方法签名存在"""
        registrar = HvoyRegistrar()
        assert hasattr(registrar, "login")
        assert hasattr(registrar, "logout")
        assert callable(registrar.login)
        assert callable(registrar.logout)

    def test_has_existing_methods(self):
        registrar = HvoyRegistrar()
        assert hasattr(registrar, "register")
        assert hasattr(registrar, "extract_invite_code")

    def test_urls_defined(self):
        assert HvoyRegistrar.REGISTER_URL == "https://hvoy.ai/user/register"
        assert HvoyRegistrar.LOGIN_URL == "https://hvoy.ai/user/login"
        assert HvoyRegistrar.INVITE_CODES_URL == "https://hvoy.ai/free-tokens/invite-codes"


class TestInviteCodeReturnType:
    """验证 extract_invite_code 返回 InviteCode 类型"""

    def test_invite_code_dataclass(self):
        code = InviteCode(code="abc123def456", source="hvoy_free_token")
        assert code.code == "abc123def456"
        assert code.source == "hvoy_free_token"
        assert code.used is False

    def test_registration_result_can_hold_invite_code(self):
        account = AccountInfo(site="hvoy", username="u", email="e@t.com", password="p")
        code = InviteCode(code="xyz", source="hvoy_free_token")
        result = RegistrationResult(site="hvoy", success=True,
                                    account=account, invite_code=code)
        assert result.success is True
        assert result.invite_code == code
        assert result.invite_code.code == "xyz"


class TestRegistrationResultNewFields:
    """验证 RegistrationResult 兼容 invite_code 和 api_key"""

    def test_asdict_includes_new_fields(self):
        account = AccountInfo(site="hvoy", username="u", email="e@t.com",
                              password="p", invite_code="ic", api_key="ak")
        d = asdict(account)
        assert d["invite_code"] == "ic"
        assert d["api_key"] == "ak"


# ====================================================================
# E2E 测试（有头模式，需要手动确认 slider + Turnstile）
# ====================================================================

@pytest.mark.e2e
class TestHvoyE2E:
    """端到端验证 hvoy 核心流程。

    运行方式：
        pytest tests/test_hvoy.py -v -m e2e --headed
    需要：
    - Chrome Profile（含 hvoy 登录态）
    - prompt 手动完成验证
    """

    @pytest.mark.skip(reason="E2E — run manually in Task 8")
    def test_register_flow(self):
        """检查 register() 方法签名和返回类型"""
        pass

    @pytest.mark.skip(reason="E2E — run manually in Task 8")
    def test_login_flow(self):
        """检查 login() 方法签名和返回类型"""
        pass

    @pytest.mark.skip(reason="E2E — run manually in Task 8")
    def test_extract_invite_code_flow(self):
        """检查 extract_invite_code() 方法签名和返回类型"""
        pass
