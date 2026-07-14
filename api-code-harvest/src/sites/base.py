class HumanVerification:
    """人工验证混入 —— 在终端暂停等待用户完成浏览器验证"""

    async def human_verification_pause(self, prompt: str) -> None:
        print()
        print("  " + "=" * 50)
        print(f"  {prompt}")
        print("  Auto-detecting captcha completion...")
        print("  " + "=" * 50)
