import random
import string
import sys

from loguru import logger


def generate_username(length: int = 12) -> str:
    """生成随机用户名，3-32位，仅含字母数字下划线连字符，不以连字符开头"""
    if length < 3 or length > 32:
        raise ValueError(f"用户名长度必须在3-32位之间，收到: {length}")
    chars = string.ascii_lowercase + string.digits
    first = random.choice(string.ascii_lowercase)
    rest = "".join(random.choices(chars + "_-", k=length - 1))
    return first + rest


def generate_password(length: int = 16) -> str:
    """生成随机密码，>=9位，包含大小写字母、数字和特殊字符"""
    if length < 9:
        raise ValueError(f"密码长度至少9位，收到: {length}")
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    specials = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    all_chars = upper + lower + digits + specials
    # 确保至少每类一个
    password = [
        random.choice(upper),
        random.choice(lower),
        random.choice(digits),
        random.choice(specials),
    ]
    password += random.choices(all_chars, k=length - 4)
    random.shuffle(password)
    return "".join(password)


def human_pause(prompt: str) -> None:
    """人工参与暂停点：打印提示并等待回车"""
    print()
    print("  " + "=" * 50)
    print(f"  {prompt}")
    print("  完成后在此终端按 Enter 继续...")
    print("  " + "=" * 50)
    input()


_logger_configured = False


def setup_logger(name: str) -> "logger":
    """配置并返回 loguru logger 实例"""
    global _logger_configured
    if not _logger_configured:
        logger.remove()
        logger.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[module]}</cyan> | <level>{message}</level>",
            level="INFO",
        )
        _logger_configured = True
    return logger.bind(module=name)
