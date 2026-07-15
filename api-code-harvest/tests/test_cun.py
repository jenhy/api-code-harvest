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
        assert CunRegistrar.LOGIN_URL == "https://www.cun.ai/sign-in"
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


class TestSliderLogic:
    """验证滑块等待逻辑参数及 force-click 修复"""

    def test_slider_timeout_default(self):
        """验证默认超时 180 秒（3 分钟）"""
        from inspect import signature
        sig = signature(CunRegistrar._wait_for_slider)
        assert sig.parameters["timeout"].default == 180

    def test_slider_login_timeout_default(self):
        from inspect import signature
        sig = signature(CunRegistrar._wait_for_slider_login)
        assert sig.parameters["timeout"].default == 180

    def test_no_force_click_on_send_button(self):
        """验证注册流程不再使用 force=True 点击发送验证码"""
        import inspect
        source = inspect.getsource(CunRegistrar.register)
        assert "force=True" not in source, "不应 force-click 已禁用的按钮"


class TestRegisterSignature:
    """验证 register() 接受 gmail_api 参数"""

    def test_register_accepts_gmail_api(self):
        from inspect import signature
        sig = signature(CunRegistrar.register)
        params = sig.parameters
        assert "gmail_api" in params
        # gmail_api 应该有一个默认值
        assert params["gmail_api"].default is None


class TestRedeemDetection:
    """验证兑换成功检测逻辑的健壮性"""

    def test_detect_redeem_success_default(self):
        """验证 _detect_redeem_success 作为静态方法存在"""
        assert hasattr(CunRegistrar, "_detect_redeem_success")
        assert callable(CunRegistrar._detect_redeem_success)

    def test_detect_success_with_success_text(self):
        result = CunRegistrar._detect_redeem_success("兑换成功")
        assert result is True

    def test_detect_success_with_check_mark(self):
        result = CunRegistrar._detect_redeem_success("✅ 兑换成功")
        assert result is True

    def test_detect_failure_with_error_text(self):
        result = CunRegistrar._detect_redeem_success("兑换失败，邀请码无效")
        assert result is False

    def test_detect_failure_with_invalid_text(self):
        result = CunRegistrar._detect_redeem_success("邀请码不存在或已使用")
        assert result is False

    def test_detect_failure_with_failed(self):
        result = CunRegistrar._detect_redeem_success("operation failed")
        assert result is False

    def test_detect_neutral_text_defaults_success_if_not_explicitly_fail(self):
        """中性的页面内容，如果没有明确失败关键词，默认视为成功"""
        result = CunRegistrar._detect_redeem_success("some random page content")
        assert result is True


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
