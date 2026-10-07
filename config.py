"""Runtime configuration loaded from environment variables (no secrets in code)."""

import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

DEFAULT_THRESHOLDS: dict[str, float] = {
    "cpu_percent": 85.0,
    "memory_percent": 85.0,
    "disk_percent": 90.0,
    "temp_celsius": 80.0,
}

THRESHOLD_LIMITS: dict[str, tuple[float, float]] = {
    "cpu_percent": (1.0, 100.0),
    "memory_percent": (1.0, 100.0),
    "disk_percent": (1.0, 100.0),
    "temp_celsius": (20.0, 150.0),
}

_THRESHOLD_ENV_VARS: dict[str, str] = {
    "cpu_percent": "MONITOR_THRESHOLD_CPU",
    "memory_percent": "MONITOR_THRESHOLD_MEMORY",
    "disk_percent": "MONITOR_THRESHOLD_DISK",
    "temp_celsius": "MONITOR_THRESHOLD_TEMP",
}

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


class ConfigError(ValueError):
    """Raised when an environment variable or submitted setting is invalid."""


@dataclass(frozen=True)
class NotifyConfig:
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_to: tuple[str, ...] = ()
    cooldown_sec: int = 1800


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    interval_sec: int
    log_file: str
    db_path: str
    retention_hours: int
    user: str
    password: Optional[str]
    thresholds: dict[str, float]
    notify: NotifyConfig


def _get_int(env: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def validate_thresholds(raw: Mapping[str, Any]) -> dict[str, float]:
    """Validate a partial threshold mapping; return floats. Raises ``ConfigError``."""
    validated: dict[str, float] = {}
    for key, value in raw.items():
        if key not in THRESHOLD_LIMITS:
            raise ConfigError(f"Unknown threshold: {key!r}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"Threshold {key!r} must be a number")
        low, high = THRESHOLD_LIMITS[key]
        if not low <= float(value) <= high:
            raise ConfigError(f"Threshold {key!r} must be between {low:g} and {high:g}")
        validated[key] = float(value)
    return validated


def _thresholds_from_env(env: Mapping[str, str]) -> dict[str, float]:
    overrides: dict[str, Any] = {}
    for key, var in _THRESHOLD_ENV_VARS.items():
        raw = env.get(var)
        if raw:
            try:
                overrides[key] = float(raw)
            except ValueError as exc:
                raise ConfigError(f"{var} must be a number, got {raw!r}") from exc
    return {**DEFAULT_THRESHOLDS, **validate_thresholds(overrides)}


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """Build ``Settings`` from environment variables (defaults are safe: loopback only)."""
    env = os.environ if env is None else env
    recipients = tuple(a.strip() for a in env.get("SMTP_TO", "").split(",") if a.strip())
    notify = NotifyConfig(
        telegram_token=env.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=env.get("TELEGRAM_CHAT_ID") or None,
        webhook_url=env.get("NOTIFY_WEBHOOK_URL") or None,
        smtp_host=env.get("SMTP_HOST") or None,
        smtp_port=_get_int(env, "SMTP_PORT", 587),
        smtp_user=env.get("SMTP_USER") or None,
        smtp_password=env.get("SMTP_PASSWORD") or None,
        smtp_from=env.get("SMTP_FROM") or None,
        smtp_to=recipients,
        cooldown_sec=_get_int(env, "NOTIFY_COOLDOWN_MIN", 30) * 60,
    )
    return Settings(
        host=env.get("MONITOR_HOST", "127.0.0.1"),
        port=_get_int(env, "MONITOR_PORT", 5000),
        interval_sec=_get_int(env, "MONITOR_INTERVAL", 10),
        log_file=env.get("MONITOR_LOG_FILE", "agent_log.txt"),
        db_path=env.get("MONITOR_DB", "agent_data.db"),
        retention_hours=_get_int(env, "MONITOR_RETENTION_HOURS", 168),
        user=env.get("MONITOR_USER", "admin"),
        password=env.get("MONITOR_PASSWORD") or None,
        thresholds=_thresholds_from_env(env),
        notify=notify,
    )
