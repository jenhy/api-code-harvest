from dataclasses import dataclass, field

import yaml


@dataclass
class BrowserConfig:
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 900
    user_agent: str = ""


@dataclass
class TimeoutConfig:
    cloudflare_challenge: int = 120
    turnstile: int = 180
    slider_puzzle: int = 180
    email_verification: int = 300
    email_code: int = 120
    page_load: int = 30


@dataclass
class RetryConfig:
    max_registration_retries: int = 2
    mail_api_retries: int = 3


@dataclass
class ModeConfig:
    flow: str = "sequential"


@dataclass
class BatchConfig:
    count: int = 1


@dataclass
class StorageConfig:
    accounts_file: str = "accounts.json"
    codes_file: str = "codes.json"
    log_file: str = "logs/harvest.log"


@dataclass
class GmailConfig:
    """Gmail REST API 配置（用于读取验证邮件）"""
    credentials_file: str = "credentials.json"
    token_pickle: str = "token.pickle"
    email_address: str = ""
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 22222


@dataclass
class Settings:
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    mode: ModeConfig = field(default_factory=ModeConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    gmail: GmailConfig = field(default_factory=GmailConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "Settings":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            browser=BrowserConfig(**data.get("browser", {})),
            timeouts=TimeoutConfig(**data.get("timeouts", {})),
            retry=RetryConfig(**data.get("retry", {})),
            mode=ModeConfig(**data.get("mode", {})),
            batch=BatchConfig(**data.get("batch", {})),
            storage=StorageConfig(**data.get("storage", {})),
            gmail=GmailConfig(**data.get("gmail", {})),
        )
