#!/usr/bin/env python3
"""
my-247-worker: 24/7 系統監控代理
負責監控電腦狀態、分析數據(cpu/memory/disk/network/temperature)、記錄日誌，並顯示在網頁上。
"""

import hmac
import logging
import socket
import sys
import threading
import time
from datetime import datetime
from typing import Any, Optional

import psutil
from flask import Flask, Response, jsonify, render_template, request

from analysis import build_stats, detect_anomalies
from collectors import collect_snapshot, collect_top_processes
from config import ConfigError, LOOPBACK_HOSTS, Settings, load_settings, validate_thresholds
from history import build_history, compute_rate_kbps
from logbook import LogBook
from notifier import Notifier, build_notifier
from storage import MetricsStore
from temperature import TemperatureReader
from gpu import GPUMonitor

logger = logging.getLogger(__name__)

PRUNE_EVERY_SEC = 3600
DEFAULT_HISTORY_MINUTES = 15


class MonitorState:
    """Latest readings shared between the monitor thread and web handlers."""

    def __init__(self, thresholds: dict[str, float]) -> None:
        self._lock = threading.Lock()
        self._thresholds = dict(thresholds)
        self._data: dict[str, Any] = {
            "stats": {}, "anomalies": [], "disks": [], "cores": [], "processes": [], "temp_source": None,
        }

    def update(self, **fields: Any) -> None:
        with self._lock:
            self._data.update(fields)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {**self._data, "thresholds": dict(self._thresholds)}

    def get_thresholds(self) -> dict[str, float]:
        with self._lock:
            return dict(self._thresholds)

    def set_thresholds(self, updates: dict[str, float]) -> dict[str, float]:
        with self._lock:
            self._thresholds.update(updates)
            return dict(self._thresholds)


def _utf8(value: Optional[str]) -> bytes:
    return (value or "").encode("utf-8")


def is_authorized(settings: Settings) -> bool:
    """HTTP Basic check; always True when no password is configured."""
    if not settings.password:
        return True
    auth = request.authorization
    if auth is None:
        return False
    user_ok = hmac.compare_digest(_utf8(auth.username), _utf8(settings.user))
    pass_ok = hmac.compare_digest(_utf8(auth.password), _utf8(settings.password))
    return user_ok and pass_ok


def create_app(settings: Settings, store: MetricsStore, state: MonitorState, logbook: LogBook) -> Flask:
    app = Flask(__name__)

    @app.before_request
    def require_auth() -> Optional[Response]:
        if request.path == "/health" or is_authorized(settings):
            return None
        return Response("需要登入", 401, {"WWW-Authenticate": 'Basic realm="247 Monitor"'})

    @app.route("/")
    def dashboard() -> str:
        return render_template("index.html")

    @app.route("/api/data")
    def api_data() -> Response:
        max_minutes = settings.retention_hours * 60
        minutes = request.args.get("minutes", default=DEFAULT_HISTORY_MINUTES, type=int)
        minutes = max(1, min(minutes, max_minutes))
        rows = store.query(int(time.time()) - minutes * 60)
        return jsonify({**state.snapshot(), "history": build_history(rows, minutes), "minutes": minutes})

    @app.route("/api/logs")
    def api_logs() -> Response:
        return jsonify({"logs": logbook.recent()})

    @app.route("/api/export")
    def api_export() -> Response:
        import csv
        import io
        days = request.args.get("days", default=1, type=int)
        rows = store.query(int(time.time()) - days * 86400)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "CPU(%)", "Memory(%)", "Disk_Max(%)", "Temp(C)", "Net_Sent", "Net_Recv"])
        for r in rows:
            dt = datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([dt, r[1], r[2], r[3], r[4], r[5], r[6]])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=export_{int(time.time())}.csv"}
        )

    @app.route("/api/thresholds", methods=["GET", "POST"])
    def api_thresholds() -> Any:
        if request.method == "GET":
            return jsonify(state.get_thresholds())
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not payload:
            return jsonify({"error": "請提供 JSON 物件"}), 400
        try:
            updates = validate_thresholds(payload)
        except ConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        merged = state.set_thresholds(updates)
        store.save_thresholds(merged)
        logbook.write(f"閥值已更新: {updates}")
        return jsonify(merged)

    @app.route("/health")
    def health() -> Response:
        return jsonify({"status": "ok", "time": datetime.now().isoformat()})

    return app


def monitor_loop(
    settings: Settings,
    store: MetricsStore,
    state: MonitorState,
    logbook: LogBook,
    notifier: Notifier,
    gpu_monitor: GPUMonitor,
) -> None:
    """背景監控循環。"""
    temp_reader = TemperatureReader()
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")
    hostname = socket.gethostname()
    prev: Optional[tuple[int, int, int]] = None  # (ts, bytes_sent, bytes_recv)
    last_prune = 0.0

    logbook.write("247 worker 監控代理已啟動")

    while True:
        try:
            snapshot = collect_snapshot(temp_reader, gpu_monitor)
            thresholds = state.get_thresholds()

            sent_bps = recv_bps = 0.0
            if prev is not None:
                sent_kbps = compute_rate_kbps(prev[0], snapshot.ts, prev[1], snapshot.net_sent)
                recv_kbps = compute_rate_kbps(prev[0], snapshot.ts, prev[2], snapshot.net_recv)
                sent_bps = (sent_kbps or 0.0) * 1024
                recv_bps = (recv_kbps or 0.0) * 1024
            prev = (snapshot.ts, snapshot.net_sent, snapshot.net_recv)

            anomalies = detect_anomalies(snapshot, thresholds)
            disk_max = max((d["percent"] for d in snapshot.disks), default=0.0)

            store.insert((snapshot.ts, snapshot.cpu, snapshot.memory, disk_max,
                          snapshot.temp_c, snapshot.net_sent, snapshot.net_recv))
            state.update(
                stats=build_stats(snapshot, thresholds, sent_bps, recv_bps, boot_time),
                anomalies=anomalies,
                disks=snapshot.disks,
                cores=snapshot.cores,
                processes=collect_top_processes(),
                temp_source=snapshot.temp_source,
                gpu=snapshot.gpu,
            )

            if anomalies:
                for anomaly in anomalies:
                    logbook.write(f"🚨 異常檢測: {anomaly}", level="WARN")
                    notifier.notify(anomaly, f"🚨 247 監控異常 ({hostname})", anomaly)
            else:
                logbook.write("監控執行: 無異常")

            if time.monotonic() - last_prune > PRUNE_EVERY_SEC:
                removed = store.prune(int(time.time()) - settings.retention_hours * 3600)
                last_prune = time.monotonic()
                if removed:
                    logbook.write(f"已清除 {removed} 筆過期歷史資料")

        except Exception as exc:  # keep the 24/7 loop alive; failure is logged below
            logger.exception("Monitor iteration failed")
            logbook.write(f"❌ 監控錯誤: {exc}", level="ERROR")

        time.sleep(settings.interval_sec)


def main() -> None:
    # 確保 stdout 可以輸出中文（Windows 預設為 cp1252）
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        settings = load_settings()
    except ConfigError as exc:
        sys.exit(f"設定錯誤: {exc}")

    if settings.host not in LOOPBACK_HOSTS and not settings.password:
        logger.warning("MONITOR_HOST=%s 對外開放但未設定 MONITOR_PASSWORD，任何人都能存取儀表板！", settings.host)

    store = MetricsStore(settings.db_path)
    saved = store.load_thresholds()
    try:
        thresholds = {**settings.thresholds, **validate_thresholds(saved)}
    except ConfigError as exc:
        logger.warning("Ignoring invalid saved thresholds: %s", exc)
        thresholds = dict(settings.thresholds)

    state = MonitorState(thresholds)
    logbook = LogBook(settings.log_file)
    notifier = build_notifier(settings.notify)
    if notifier.enabled:
        logbook.write("通知管道: " + ", ".join(name for name, _ in notifier.channels))

    gpu_monitor = GPUMonitor()
    if gpu_monitor.enabled:
        logbook.write(f"GPU 監控已啟動: {gpu_monitor.name}")

    threading.Thread(
        target=monitor_loop, args=(settings, store, state, logbook, notifier, gpu_monitor), daemon=True
    ).start()

    app = create_app(settings, store, state, logbook)
    app.run(host=settings.host, port=settings.port, threaded=True)


if __name__ == "__main__":
    main()
