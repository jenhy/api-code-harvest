"""Gmail REST API client — search & read verification emails via OAuth."""
import base64
import os
import pickle
import re
import time

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailApi:
    """Gmail API client, proxied for GFW bypass.

    Usage:
        api = GmailApi("credentials.json", "token.pickle",
                       proxy_host="127.0.0.1", proxy_port=22222)
        link = api.wait_for_verification_link(
            query="from:noreply@hvoy.ai", domain="hvoy.ai")
        code = api.wait_for_verification_code(
            query="to:alias@gmail.com")
    """

    def __init__(self, credentials_file: str, token_pickle: str,
                 proxy_host: str = "127.0.0.1", proxy_port: int = 22222):
        self.credentials_file = credentials_file
        self.token_pickle = token_pickle
        self.proxy = f"http://{proxy_host}:{proxy_port}"
        self._service = None

    # ------------------------------------------------------------------
    # 认证
    # ------------------------------------------------------------------

    def _auth(self):
        """Authenticate with Gmail API via OAuth. Caches token.pickle.

        Uses save/restore pattern for HTTPS_PROXY to avoid global env pollution.
        """
        # 保存原始环境变量
        saved_https_proxy = os.environ.pop("HTTPS_PROXY", None)
        saved_http_proxy = os.environ.pop("HTTP_PROXY", None)

        os.environ["HTTPS_PROXY"] = self.proxy
        os.environ["HTTP_PROXY"] = self.proxy

        try:
            creds = None
            if os.path.exists(self.token_pickle):
                with open(self.token_pickle, "rb") as f:
                    creds = pickle.load(f)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                with open(self.token_pickle, "wb") as f:
                    pickle.dump(creds, f)
            return creds
        finally:
            # 恢复原始环境变量
            if saved_https_proxy is not None:
                os.environ["HTTPS_PROXY"] = saved_https_proxy
            else:
                os.environ.pop("HTTPS_PROXY", None)
            if saved_http_proxy is not None:
                os.environ["HTTP_PROXY"] = saved_http_proxy
            else:
                os.environ.pop("HTTP_PROXY", None)

    @property
    def service(self):
        if self._service is None:
            creds = self._auth()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    # ------------------------------------------------------------------
    # 邮件搜索 & 正文
    # ------------------------------------------------------------------

    def search_messages(self, query: str, max_results: int = 5) -> list[dict]:
        """Search messages by query. Returns [{id, from, subject, snippet, to}]."""
        result = self.service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = result.get("messages", [])
        out = []
        for msg in messages:
            detail = self.service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "To"]
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            out.append({
                "id": msg["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "to": headers.get("To", ""),
                "snippet": detail.get("snippet", ""),
            })
        return out

    def get_email_body(self, msg_id: str) -> str:
        """Get full HTML body of a message."""
        detail = self.service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        return self._extract_body(detail["payload"])

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Recursively extract body text from MIME parts."""
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(
                payload["body"]["data"]
            ).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            result = GmailApi._extract_body(part)
            if result:
                return result
        return ""

    # ------------------------------------------------------------------
    # 轮询等待
    # ------------------------------------------------------------------

    def wait_for_verification_link(self, query: str, domain: str,
                                    timeout: int = 120,
                                    poll_interval: int = 5) -> str | None:
        """Poll for email matching query, extract verification link containing domain."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msgs = self.search_messages(query, max_results=3)
            for msg in msgs:
                body = self.get_email_body(msg["id"])
                link = self._extract_link(body, domain)
                if link:
                    return link
            time.sleep(poll_interval)
        return None

    def wait_for_verification_code(self, query: str,
                                    timeout: int = 120,
                                    poll_interval: int = 5) -> str | None:
        """Poll for email matching query, extract 6-digit verification code."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msgs = self.search_messages(query, max_results=3)
            for msg in msgs:
                body = self.get_email_body(msg["id"])
                code = self._extract_code(body)
                if code:
                    return code
            time.sleep(poll_interval)
        return None

    # ------------------------------------------------------------------
    # 静态提取方法（纯逻辑，可单独测试）
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_link(html: str, domain_hint: str) -> str | None:
        """Extract verification link: href with verify-email?token= and domain_hint.

        Tries:
        1. Match URLs containing 'verify-email?token=' + domain_hint
        2. Fallback: any URL on the page containing domain_hint
        """
        # 优先：verify-email?token= 模式
        pattern = r'https://[^\s"\'<>]*verify-email\?token=[a-f0-9]+[^\s"\'<>]*'
        links = re.findall(pattern, html)
        for link in links:
            if domain_hint in link:
                return link
        # 兜底：任何包含 domain_hint 的链接
        all_links = re.findall(r'https?://[^\s"\'<>]+', html)
        for link in all_links:
            if domain_hint in link:
                return link
        return None

    @staticmethod
    def _extract_code(html: str) -> str | None:
        """Extract 6-digit code from email body."""
        m = re.search(r'\b(\d{6})\b', html)
        return m.group(1) if m else None
