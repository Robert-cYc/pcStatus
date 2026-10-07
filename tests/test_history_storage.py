import time

from history import build_history, compute_rate_kbps, downsample
from storage import MetricsStore


def test_compute_rate_normal() -> None:
    assert compute_rate_kbps(0, 10, 0, 10240) == 1.0


def test_compute_rate_reset_gap_and_bad_time() -> None:
    assert compute_rate_kbps(0, 10, 500, 100) is None      # counter reset
    assert compute_rate_kbps(0, 1000, 0, 10) is None       # long gap
    assert compute_rate_kbps(10, 10, 0, 10) is None        # zero elapsed


def test_downsample_keeps_newest() -> None:
    items = list(range(100))
    result = downsample(items, 10)
    assert len(result) <= 10
    assert result[-1] == 99


def test_downsample_short_list_unchanged() -> None:
    assert downsample([1, 2, 3], 10) == [1, 2, 3]


def test_build_history_rates_and_nulls() -> None:
    rows = [
        (1000, 10.0, 50.0, 60.0, None, 0, 0),
        (1010, 20.0, 51.0, 60.0, 55.5, 10240, 20480),
    ]
    history = build_history(rows, minutes=15)
    assert history["cpu"] == [10.0, 20.0]
    assert history["temp"] == [None, 55.5]
    assert history["net_sent_kbps"] == [None, 1.0]
    assert history["net_recv_kbps"] == [None, 2.0]


def test_build_history_empty() -> None:
    assert build_history([], minutes=5)["cpu"] == []


def test_store_insert_query_prune(tmp_path) -> None:
    store = MetricsStore(str(tmp_path / "m.db"))
    now = int(time.time())
    store.insert((now - 100, 1.0, 2.0, 3.0, None, 10, 20))
    store.insert((now, 4.0, 5.0, 6.0, 40.0, 30, 40))
    assert len(store.query(now - 200)) == 2
    assert len(store.query(now - 50)) == 1
    assert store.prune(now - 50) == 1
    assert len(store.query(0)) == 1
    store.close()


def test_store_thresholds_persist(tmp_path) -> None:
    path = str(tmp_path / "m.db")
    store = MetricsStore(path)
    assert store.load_thresholds() == {}
    store.save_thresholds({"cpu_percent": 70.0})
    store.close()
    assert MetricsStore(path).load_thresholds() == {"cpu_percent": 70.0}
