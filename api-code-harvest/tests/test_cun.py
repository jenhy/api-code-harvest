"""CunRegistrar 测试 — 单元测试 + E2E 框架

⚠️ E2E 测试需要真实 Chrome Profile + 有头浏览器，Task 8 手动执行。
"""
import pytest

from src.models import AccountInfo, RegistrationResult
from src.sites.cun import CunRegistrar


class TestCunRegistrarInstance:
    """验证 CunRegistrar 包含新增方法"""

    def test_importable(self):
        registrar = CunRegistrar()
        assert isinstance(registrar, CunRegistrar)

    def test_has_all_methods(self):
        registrar = CunRegistrar()
        # 新增方法
        assert hasattr(registrar, "login")
        assert callable(registrar.login)
        assert hasattr(registrar, "redeem_invite_code")
        assert callable(registrar.redeem_invite_code)
        assert hasattr(registrar, "create_api_key")
        assert callable(registrar.create_api_key)
        assert hasattr(registrar, "logout")
        assert callable(registrar.logout)
        assert hasattr(registrar, "register")
        assert callable(registrar.register)

    def test_urls_defined(self):
        assert CunRegistrar.REGISTER_URL == "https://www.cun.ai/sign-up"
        assert CunRegistrar.LOGIN_URL == "https://www.cun.ai/login"
        assert CunRegistrar.WALLET_URL == "https://www.cun.ai/wallet"


class TestCunRegistrationResult:
    """验证 CUN 注册结果可以包含扩展字段"""

    def test_registration_result_with_invite_code(self):
        account = AccountInfo(site="cun", username="u", email="e@t.com",
                              password="p", invite_code="ic", api_key="")
        result = RegistrationResult(site="cun", success=True, account=account)
        assert result.success
        assert result.account.invite_code == "ic"

    def test_registration_result_with_api_key(self):
        account = AccountInfo(site="cun", username="u", email="e@t.com",
                              password="p", api_key="sk-test123")
        result = RegistrationResult(site="cun", success=True, account=account)
        assert result.account.api_key == "sk-test123"


class TestSliderWaitLogic:
    """验证滑块等待逻辑参数"""

    def test_slider_timeout_default(self):
        """验证默认超时 180 秒（3 分钟）"""
        from inspect import signature
        sig = signature(CunRegistrar._wait_for_slider)
        assert sig.parameters["timeout"].default == 180

    def test_slider_login_timeout_default(self):
        from inspect import signature
        sig = signature(CunRegistrar._wait_for_slider_login)
        assert sig.parameters["timeout"].default == 180


class TestRegisterSignature:
    """验证 register() 接受 gmail_api 参数"""

    def test_register_accepts_gmail_api(self):
        from inspect import signature
        sig = signature(CunRegistrar.register)
        params = sig.parameters
        assert "gmail_api" in params
        # gmail_api 应该有一个默认值
        assert params["gmail_api"].default is None


@pytest.mark.e2e
class TestCunE2E:
    """端到端验证 CUN 核心流程。

    运行方式：
        pytest tests/test_cun.py -v -m e2e --headed
    """

    @pytest.mark.skip(reason="E2E — run manually in Task 8")
    def test_register_flow(self):
        pass

    @pytest.mark.skip(reason="E2E — run manually in Task 8")
    def test_login_flow(self):
        pass

    @pytest.mark.skip(reason="E2E — run manually in Task 8")
    def test_redeem_and_create_key_flow(self):
        pass
