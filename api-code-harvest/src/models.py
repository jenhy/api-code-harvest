from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AccountInfo:
    site: str
    username: str
    email: str
    password: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    verified: bool = False
    invite_code: str = ""
    api_key: str = ""


@dataclass
class InviteCode:
    code: str
    source: str
    obtained_at: str = field(default_factory=lambda: datetime.now().isoformat())
    used: bool = False
    used_by: str | None = None


@dataclass
class RegistrationResult:
    site: str
    success: bool
    account: AccountInfo | None = None
    invite_code: InviteCode | None = None
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class BatchResult:
    total: int
    success: int
    failed: int
    results: list[RegistrationResult] = field(default_factory=list)
    codes_obtained: list[InviteCode] = field(default_factory=list)
