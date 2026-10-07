# 247 系統監控台 (siAgent) 🚀

![Dashboard Preview](https://img.shields.io/badge/UI-Dark%20Mode-22d3ee?style=for-the-badge)
![Build Status](https://img.shields.io/github/actions/workflow/status/Robert-cYc/pcStatus/build.yml?style=for-the-badge)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge)

siAgent 是一個輕量、美觀且功能強大的 **24/7 背景系統監控代理**。它會在你電腦的背景靜默運行，並提供一個精美的本地網頁儀表板，讓你隨時掌握機器的健康狀態。

## ✨ 核心特色

- **📊 現代化網頁儀表板**: 極致的深色模式 (Dark Mode) UI，內建流暢的即時折線圖 (Chart.js)。
- **🚀 零依賴單一執行檔**: 支援打包成獨立的 `siAgent.exe`，免裝 Python、隨插即用！
- **💻 全方位硬體監控**:
  - **CPU & 記憶體**: 即時負載、單核使用率與高耗能程序排行。
  - **GPU 監控**: 支援 NVIDIA 顯示卡使用率、VRAM 佔用與溫度追蹤 (需支援 NVML)。
  - **網路流量**: 精準監控即時的網路發送 (Upload) 與接收 (Download) 速率。
  - **溫度偵測**: 支援讀取 CPU 與系統溫度 (Windows 環境推薦搭配 LibreHardwareMonitor)。
  - **磁碟空間**: 各分割區容量追蹤。
- **🚨 異常警報系統**: 支援自訂閥值，觸發時可透過 Webhook/Telegram 等發送通知。
- **💾 歷史資料與匯出**: 自動將數據記錄至本地 SQLite，並支援一鍵匯出過去 24 小時的 `.csv` 報表。

---

## 📥 快速啟動 (使用 Executable)

如果您不想安裝任何環境，只需下載編譯好的執行檔：

1. 到本專案的 **[GitHub Actions](https://github.com/Robert-cYc/pcStatus/actions)** 頁面。
2. 點擊最新的 "Build Windows Executable" 成功紀錄。
3. 下載 Artifacts 區塊中的 `siAgent-Windows-Executable`。
4. 解壓縮並雙擊執行 `siAgent.exe`。
5. 程式會在背景啟動，並自動在瀏覽器開啟儀表板 `http://127.0.0.1:8100`。

> 💡 **自動構建機制**: 每當程式碼推送到 `main` 分支時，GitHub Actions 會自動編譯並產出最新的 `.exe` 供下載！

---

## 🛠️ 開發與手動執行 (Python 環境)

如果你想修改原始碼或手動執行：

### 1. 安裝依賴
```bash
git clone https://github.com/Robert-cYc/pcStatus.git
cd pcStatus
pip install -r requirements.txt
```

### 2. 啟動服務
**Windows 用戶可以直接點擊 `start.bat`**。或者使用指令：
```bash
python monitor.py
```

### 3. 編譯自己的執行檔
只需執行：
```bash
build.bat
```
編譯完成後，獨立的 `.exe` 檔案會出現在 `dist/` 資料夾中。

---

## ⚙️ 系統設定與環境變數

你可以複製 `local_env.bat.example` 並更名為 `local_env.bat`，來設定自訂環境變數 (例如綁定 IP、修改 Port、設定密碼與通知頻道)：

```bat
:: 設定綁定的 IP 與 Port (0.0.0.0 可讓區網其他電腦連線)
set MONITOR_HOST=0.0.0.0
set MONITOR_PORT=8100

:: 若開放區網，建議設定密碼保護儀表板
set MONITOR_USER=admin
set MONITOR_PASSWORD=your_secure_password

:: 異常通知設定 (例如發送至 Telegram)
set MONITOR_NOTIFY=tg://bot_token/chat_id
```

## 🌡️ 關於溫度偵測 (Windows)
Windows 預設無法直接透過 Python 取得精準的硬體溫度。我們推薦在背景執行 [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)，並在選項中開啟 `Web Server` (預設 Port 8085)。siAgent 會自動偵測並讀取其溫度數據！

---

*Designed with ❤️ by Antigravity AI*
