from notifier import Notifier


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_no_channels_never_sends() -> None:
    notifier = Notifier([], cooldown_sec=60, background=False)
    assert notifier.enabled is False
    assert notifier.notify("k", "s", "b") is False


def test_cooldown_per_key() -> None:
    sent: list[tuple[str, str]] = []
    clock = FakeClock()
    notifier = Notifier([("fake", lambda s, b: sent.append((s, b)))], cooldown_sec=60, clock=clock, background=False)

    assert notifier.notify("cpu", "subj", "body") is True
    assert notifier.notify("cpu", "subj", "body") is False   # within cooldown
    assert notifier.notify("mem", "subj", "body") is True    # different key
    clock.now += 61
    assert notifier.notify("cpu", "subj", "body") is True    # cooldown elapsed
    assert len(sent) == 3


def test_channel_failure_does_not_block_others() -> None:
    sent: list[str] = []

    def failing(subject: str, body: str) -> None:
        raise OSError("network down")

    notifier = Notifier(
        [("bad", failing), ("good", lambda s, b: sent.append(b))],
        cooldown_sec=60, background=False,
    )
    assert notifier.notify("k", "s", "b") is True
    assert sent == ["b"]
