#!/bin/bash
# setup.sh — vc01-rpi3 開發環境安裝腳本
# 執行方式: sudo bash setup.sh

set -e

echo "=== vc01-rpi3 開發環境安裝開始 ==="
echo ""

# ── Node.js v22 ───────────────────────────────────────────────────
echo "[1/7] 安裝 Node.js v22..."
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
node -v && npm -v
echo "完成"; echo ""
# ── Claude Code ───────────────────────────────────────────────────
echo "[2/7] 安裝 Claude Code..."
npm install -g @anthropic-ai/claude-code
claude --version
echo "完成"; echo ""

# ── Claude 登入 ───────────────────────────────────────────────────
echo "[3/7] Claude 登入"
echo "請執行以下指令完成 Claude 登入："
echo "    claude"
echo "登入完成後按 Ctrl+C，再按 Enter 繼續。"
echo ""
read -r -p "已登入 Claude？按 Enter 繼續..."
echo ""
# ── Python 套件 ───────────────────────────────────────────────────
echo "[4/7] 安裝 Python 套件到 ~/fastapi-env..."
sudo -u pi /home/pi/fastapi-env/bin/pip install flask flask-cors
echo "完成"; echo ""

# ── 初始化 tpms_settings.json ─────────────────────────────────────
echo "[5/7] 初始化 tpms_settings.json..."
chown pi:pi /home/pi/vc01-rpi3/tpms_settings.json 2>/dev/null || true
python3 /home/pi/vc01-rpi3/reset_settings.py
echo "完成"; echo ""
# ── tpms_server systemd 服務 ──────────────────────────────────────
echo "[6/7] 設定 tpms_server systemd 服務..."
cat > /etc/systemd/system/tpms_server.service << 'EOF'
[Unit]
Description=TPMS BLE Flask Server
After=network.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/vc01-rpi3
ExecStart=/home/pi/fastapi-env/bin/python3 /home/pi/vc01-rpi3/tpms_server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable tpms_server
systemctl start tpms_server
systemctl status tpms_server --no-pager
echo "完成"; echo ""
# ── 藍牙啟用 ──────────────────────────────────────────────────────
echo "[7/7] 啟用藍牙..."
rfkill unblock bluetooth
systemctl enable bluetooth
systemctl start bluetooth
echo "完成"; echo ""

echo "============================================"
echo "  開發環境安裝完成！"
echo "============================================"
echo ""
echo "服務狀態："
echo "  tpms_server : http://localhost:5000"
echo "  systemctl status tpms_server"
echo ""
echo "Claude Code:"
echo "  cd ~/vc01-rpi3 && claude"
echo ""
