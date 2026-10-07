# my-247-worker

24/7 系統監控代理 — 監控 CPU / 記憶體 / 硬碟 / 溫度 / 網路，分析異常、發送通知、記錄日誌，並顯示在網頁儀表板。

## 功能

- 📊 每 10 秒收集資源數據，**歷史資料存入 SQLite**（重啟不遺失，預設保留 7 天）
- 📈 趨勢圖表可切換 **5 分鐘 / 15 分鐘 / 1 小時 / 6 小時 / 24 小時**
- 🧠 CPU 各核心使用率、💽 **所有磁碟分割區**、🔥 高負載程序 Top 8
- 🌡️ CPU 溫度偵測（見「溫度感測器」）
- 🚨 異常檢測，**閥值可在網頁右上角「閥值設定」調整**並自動保存
- 🔔 異常通知：Telegram / Webhook (Slack、Discord…) / Email，每種異常有冷卻時間避免洗版
- 🔒 可選的 HTTP Basic 登入；預設只監聽 `127.0.0.1`
- 📦 Chart.js 已內建於 `static/vendor/`，離線可用
- 📝 日誌寫入 `agent_log.txt`（超過 5 MB 自動輪替）

## 快速開始

```bash
pip install -r requirements.txt
python monitor.py
```

開啟瀏覽器 → `http://localhost:5000`

## 設定（環境變數）

| 變數 | 預設 | 說明 |
|------|------|------|
| `MONITOR_HOST` | `127.0.0.1` | 設為 `0.0.0.0` 對外開放（**務必同時設定密碼**） |
| `MONITOR_PORT` | `5000` | 連接埠 |
| `MONITOR_INTERVAL` | `10` | 取樣間隔（秒） |
| `MONITOR_USER` / `MONITOR_PASSWORD` | `admin` / 空 | 設定密碼即啟用登入（`/health` 不需登入） |
| `MONITOR_DB` | `agent_data.db` | SQLite 路徑 |
| `MONITOR_RETENTION_HOURS` | `168` | 歷史保留時數 |
| `MONITOR_LOG_FILE` | `agent_log.txt` | 日誌檔 |
| `MONITOR_THRESHOLD_CPU` / `_MEMORY` / `_DISK` / `_TEMP` | 85 / 85 / 90 / 80 | 初始閥值（網頁修改後以網頁為準） |
| `LHM_URL` | 空 | LibreHardwareMonitor 溫度來源 |

### 通知管道

| 管道 | 需要的變數 |
|------|-----------|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Webhook | `NOTIFY_WEBHOOK_URL`（同時送出 `text` 與 `content` 欄位，相容 Slack / Discord） |
| Email | `SMTP_HOST`, `SMTP_PORT`(587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`（逗號分隔） |
| 冷卻時間 | `NOTIFY_COOLDOWN_MIN`（預設 30 分鐘） |

> LINE Notify 已於 2025-03 終止服務，請改用 Telegram 或 Webhook。
> 機密資訊只放環境變數，不要寫入程式碼或提交到 Git。

範例（PowerShell）：

```powershell
$env:MONITOR_HOST = "0.0.0.0"
$env:MONITOR_PASSWORD = "請換成強密碼"
$env:TELEGRAM_BOT_TOKEN = "..."
$env:TELEGRAM_CHAT_ID = "..."
python monitor.py
```

## 溫度感測器

依序嘗試以下來源，皆不可用時儀表板顯示 `N/A`：

1. `psutil.sensors_temperatures()` — Linux / FreeBSD。
2. **LibreHardwareMonitor** (Windows 建議) — 開啟 Options → Remote Web Server → Run，然後設定 `LHM_URL`：
   ```powershell
   $env:LHM_URL = "http://localhost:8085/data.json"
   ```
3. Windows ACPI Thermal Zone (WMI) — 多數桌機不支援，部分需系統管理員權限。

## 測試

```bash
pip install -r requirements-dev.txt
pytest
```

## 專案結構

| 檔案 | 用途 |
|------|------|
| `monitor.py` | Flask app 與背景監控迴圈 |
| `collectors.py` | psutil 採集（核心、磁碟、程序） |
| `analysis.py` | 異常判斷與顯示格式（純函式） |
| `temperature.py` | 溫度來源 |
| `storage.py` / `history.py` | SQLite 與趨勢資料轉換 |
| `notifier.py` | 通知管道與冷卻 |
| `config.py` | 環境變數與閥值驗證 |
| `logbook.py` | 日誌檔與輪替 |

## API 端點

| 路徑 | 說明 |
|------|------|
| `/` | 網頁儀表板 |
| `/api/data?minutes=15` | 即時數據、核心、磁碟、程序、歷史趨勢 |
| `/api/thresholds` | `GET` 讀取 / `POST` JSON 更新閥值 |
| `/api/logs` | 最近日誌 |
| `/health` | 健康檢查（免登入） |

## 注意事項

- 若專案位於 Google Drive 等雲端同步資料夾，SQLite 檔案可能在同步時被鎖定；可用 `MONITOR_DB` 指向本機路徑（如 `C:\data\agent_data.db`）。
- 內建 Flask 為開發用伺服器；長期對外服務建議搭配反向代理與 HTTPS（Basic 登入在 HTTP 下是明碼傳輸）。

## 日誌格式

```
2026-10-07 11:21:19  247 worker 監控代理已啟動
2026-10-07 11:21:20  🚨 異常檢測: 記憶體使用率超過 85% 閥值
2026-10-07 11:21:31  監控執行: 無異常
```
