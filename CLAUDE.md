# vc01-rpi3 專案

## 硬體
- Raspberry Pi 3B, 32GB MicroSD
- Bluetooth 內建（BLE Advertising）
- Wi-Fi: 2.4GHz only

## 作業系統
- Raspberry Pi OS Lite 64-bit Trixie (Debian 13)
- Kernel: 6.12.75+rpt-rpi-v8
- 帳號: pi, 家目錄: /home/pi/

## 網路
- Hostname: vc00-rpi3-da91 (動態 MAC 後四碼)
- mDNS: vc00-rpi3-da91.local
- SSH: ssh pi@vc00-rpi3-da91.local
- Hotspot: vc00-rpi3-$MAC / 192.168.100.1 (無密碼)
- 已儲存 Wi-Fi: VC_AP, Unison-tech, VC_iPhone

## Python 環境
- Python 3.13.5
- venv: ~/fastapi-env
- 套件: FastAPI, uvicorn, Flask, flask-cors
- FastAPI: port 8000 (systemd 自動啟動)

## 專案結構
- ~/vc01-rpi3/tpms_server.py — TPMS BLE Flask Server (port 5000)
- ~/vc01-rpi3/templates/tpms_ui.html — Web HMI
- ~/vc01-rpi3/tpms_settings.json — 設定檔

## TPMS 規格
- BLE Advertising, GFSK, 1Mbps, -4dBm
- Manufacturer Data 15 bytes
- CRC16: POLY=0x8005, INIT=0xFFFF, REFIN/REFOUT=False
- 輪胎位置: FL=0x03, FR=0x01, RL=0x04, RR=0x02
- 氣壓: raw×3.13/100=Bar
- 溫度: raw-50=°C
- 電壓: raw×0.01+1.22=V

## 開發規範
- Python 統一使用 ~/fastapi-env
- 服務用 systemd 管理
- 語言: 繁體中文溝通

## 待辦
- [x] tpms_server systemd 開機自動啟動
- [x] 驗證 BLE 訊號 (nRF Connect)
- [x] Web HMI 優化
- SQLite 資料儲存
