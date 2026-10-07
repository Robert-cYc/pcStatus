import pytest

from config import ConfigError, DEFAULT_THRESHOLDS, load_settings, validate_thresholds


def test_defaults_are_safe() -> None:
    settings = load_settings({})
    assert settings.host == "127.0.0.1"
    assert settings.password is None
    assert settings.thresholds == DEFAULT_THRESHOLDS
    assert settings.notify.cooldown_sec == 1800


def test_env_overrides() -> None:
    settings = load_settings({
        "MONITOR_HOST": "0.0.0.0", "MONITOR_PORT": "8080", "MONITOR_PASSWORD": "s3cret",
        "MONITOR_THRESHOLD_CPU": "70", "SMTP_TO": "a@x.com, b@x.com", "NOTIFY_COOLDOWN_MIN": "5",
    })
    assert settings.host == "0.0.0.0"
    assert settings.port == 8080
    assert settings.password == "s3cret"
    assert settings.thresholds["cpu_percent"] == 70.0
    assert settings.notify.smtp_to == ("a@x.com", "b@x.com")
    assert settings.notify.cooldown_sec == 300


def test_invalid_int_raises() -> None:
    with pytest.raises(ConfigError):
        load_settings({"MONITOR_PORT": "abc"})


def test_invalid_threshold_env_raises() -> None:
    with pytest.raises(ConfigError):
        load_settings({"MONITOR_THRESHOLD_CPU": "150"})


@pytest.mark.parametrize("payload", [
    {"cpu_percent": 0},
    {"cpu_percent": "80"},
    {"cpu_percent": True},
    {"unknown": 10},
    {"temp_celsius": 500},
])
def test_validate_thresholds_rejects(payload: dict) -> None:
    with pytest.raises(ConfigError):
        validate_thresholds(payload)


def test_validate_thresholds_accepts_partial() -> None:
    assert validate_thresholds({"cpu_percent": 70, "temp_celsius": 75.5}) == {"cpu_percent": 70.0, "temp_celsius": 75.5}
