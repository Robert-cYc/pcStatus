"""Alert notifications with per-alert cooldown. Channels are configured via environment."""

import json
import logging
import smtplib
import threading
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Callable

from config import NotifyConfig

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SEC = 10

Channel = Callable[[str, str], None]  # (subject, body)


def _telegram_channel(token: str, chat_id: str) -> Channel:
    def send(subject: str, body: str) -> None:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": f"{subject}\n{body}"}).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        with urllib.request.urlopen(url, data=data, timeout=HTTP_TIMEOUT_SEC):
            pass
    return send


def _webhook_channel(url: str) -> Channel:
    def send(subject: str, body: str) -> None:
        text = f"{subject}\n{body}"
        # "text" works for Slack/Mattermost/Teams-style hooks, "content" for Discord.
        payload = json.dumps({"text": text, "content": text}).encode()
        request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SEC):
            pass
    return send


def _email_channel(cfg: NotifyConfig) -> Channel:
    def send(subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = cfg.smtp_from or cfg.smtp_user or "247-monitor@localhost"
        message["To"] = ", ".join(cfg.smtp_to)
        message.set_content(body)
        if cfg.smtp_port == 465:
            server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=HTTP_TIMEOUT_SEC)
        else:
            server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=HTTP_TIMEOUT_SEC)
            server.starttls()
        with server:
            if cfg.smtp_user and cfg.smtp_password:
                server.login(cfg.smtp_user, cfg.smtp_password)
            server.send_message(message)
    return send


class Notifier:
    """Dispatches an alert to all channels, at most once per ``cooldown_sec`` per key."""

    def __init__(
        self,
        channels: list[tuple[str, Channel]],
        cooldown_sec: int,
        clock: Callable[[], float] = time.monotonic,
        background: bool = True,
    ) -> None:
        self.channels = channels
        self._cooldown_sec = cooldown_sec
        self._clock = clock
        self._background = background
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.channels)

    def notify(self, key: str, subject: str, body: str) -> bool:
        """Send unless within cooldown. Returns True if a notification was dispatched."""
        if not self.channels:
            return False
        now = self._clock()
        with self._lock:
            last = self._last_sent.get(key)
            if last is not None and now - last < self._cooldown_sec:
                return False
            self._last_sent[key] = now
        if self._background:
            threading.Thread(target=self._send_all, args=(subject, body), daemon=True).start()
        else:
            self._send_all(subject, body)
        return True

    def _send_all(self, subject: str, body: str) -> None:
        for name, channel in self.channels:
            try:
                channel(subject, body)
            except (OSError, smtplib.SMTPException, ValueError) as exc:
                logger.warning("Notification channel %s failed: %s", name, exc)


def build_notifier(cfg: NotifyConfig) -> Notifier:
    channels: list[tuple[str, Channel]] = []
    if cfg.telegram_token and cfg.telegram_chat_id:
        channels.append(("telegram", _telegram_channel(cfg.telegram_token, cfg.telegram_chat_id)))
    if cfg.webhook_url:
        channels.append(("webhook", _webhook_channel(cfg.webhook_url)))
    if cfg.smtp_host and cfg.smtp_to:
        channels.append(("email", _email_channel(cfg)))
    return Notifier(channels, cfg.cooldown_sec)
