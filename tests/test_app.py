import base64
import dataclasses

import pytest

from collectors import collect_disks, collect_top_processes
from config import load_settings
from logbook import LogBook
from monitor import MonitorState, create_app
from storage import MetricsStore


def basic(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def make_client(tmp_path):
    stores: list[MetricsStore] = []

    def factory(password=None):
        settings = dataclasses.replace(
            load_settings({}), password=password, db_path=str(tmp_path / "t.db"), log_file=str(tmp_path / "t.log"),
        )
        store = MetricsStore(settings.db_path)
        stores.append(store)
        state = MonitorState(settings.thresholds)
        app = create_app(settings, store, state, LogBook(settings.log_file))
        return app.test_client(), store

    yield factory
    for store in stores:
        store.close()


def test_open_when_no_password(make_client) -> None:
    client, _ = make_client()
    assert client.get("/api/data").status_code == 200


def test_auth_required_but_health_open(make_client) -> None:
    client, _ = make_client(password="pw")
    assert client.get("/").status_code == 401
    assert client.get("/api/data").status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/api/data", headers=basic("admin", "wrong")).status_code == 401
    assert client.get("/api/data", headers=basic("admin", "pw")).status_code == 200


def test_non_ascii_credentials_do_not_crash(make_client) -> None:
    client, _ = make_client(password="pw")
    assert client.get("/api/data", headers=basic("管理員", "密碼")).status_code == 401


def test_data_payload_shape(make_client) -> None:
    client, _ = make_client()
    payload = client.get("/api/data?minutes=5").get_json()
    for key in ("stats", "anomalies", "disks", "cores", "processes", "thresholds", "history", "minutes"):
        assert key in payload
    assert payload["minutes"] == 5


def test_thresholds_update_persists(make_client) -> None:
    client, store = make_client()
    response = client.post("/api/thresholds", json={"cpu_percent": 70})
    assert response.status_code == 200
    assert response.get_json()["cpu_percent"] == 70.0
    assert store.load_thresholds()["cpu_percent"] == 70.0


@pytest.mark.parametrize("body", [{"cpu_percent": 0}, {"bogus": 1}, {}, [1, 2]])
def test_thresholds_rejects_invalid(make_client, body) -> None:
    client, _ = make_client()
    assert client.post("/api/thresholds", json=body).status_code == 400


def test_thresholds_requires_json(make_client) -> None:
    client, _ = make_client()
    assert client.post("/api/thresholds", data="cpu_percent=70").status_code == 400


def test_collectors_live_smoke() -> None:
    for disk in collect_disks():
        assert {"mount", "percent", "used_gb", "total_gb"} <= disk.keys()
    assert len(collect_top_processes(limit=3)) <= 3
