#!/bin/bash
# cleanup.sh — vc01-rpi3 打包前清理腳本
# 執行方式: sudo bash cleanup.sh
# 警告：此腳本會清除敏感資料，執行前請確認已備份所需檔案

set -e

echo "=== vc01-rpi3 打包前清理開始 ==="
echo "警告：此操作不可逆，將清除 SSH 金鑰、Wi-Fi 設定、歷史記錄等敏感資料"
echo ""
read -r -p "確定要繼續？(輸入 yes 確認): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "已取消清理"
    exit 0
fi
echo ""
# ── 停止服務 ──────────────────────────────────────────────────────
echo "[1/10] 停止服務..."
systemctl stop tpms_server 2>/dev/null || true
systemctl stop fastapi 2>/dev/null || true
echo "完成"; echo ""
# ── 停用並移除 fastapi 服務 ──────────────────────────────────────
echo "[2/10] 停用並移除 fastapi 服務..."
systemctl stop fastapi 2>/dev/null || true
systemctl disable fastapi 2>/dev/null || true
rm -f /etc/systemd/system/fastapi.service
rm -rf /home/pi/myapp
systemctl daemon-reload
echo "完成"; echo ""

# ── 移除 Claude Code ──────────────────────────────────────────────
echo "[3/10] 移除 Claude Code..."
npm uninstall -g @anthropic-ai/claude-code 2>/dev/null || true
rm -rf /home/pi/.claude
echo "完成"; echo ""
# ── 刪除 Wi-Fi 連線設定 ───────────────────────────────────────────
echo "[4/10] 刪除已儲存的 Wi-Fi 連線..."
for SSID in "VC_AP" "Unison-tech" "VC_iPhone"; do
    CONN=$(nmcli -t -f NAME connection show 2>/dev/null | grep -F "$SSID" || true)
    if [ -n "$CONN" ]; then
        nmcli connection delete "$CONN" 2>/dev/null && echo "  已刪除: $SSID" || true
    fi
done
echo "完成"; echo ""
# ── 清除 SSH 金鑰 ─────────────────────────────────────────────────
echo "[5/10] 清除 SSH keys..."
truncate -s 0 /home/pi/.ssh/authorized_keys 2>/dev/null || true
truncate -s 0 /home/pi/.ssh/known_hosts 2>/dev/null || true
truncate -s 0 /root/.ssh/authorized_keys 2>/dev/null || true
truncate -s 0 /root/.ssh/known_hosts 2>/dev/null || true
echo "完成"; echo ""

# ── 清除歷史記錄 ──────────────────────────────────────────────────
echo "[6/10] 清除 bash / python history..."
truncate -s 0 /home/pi/.bash_history 2>/dev/null || true
truncate -s 0 /root/.bash_history 2>/dev/null || true
truncate -s 0 /home/pi/.python_history 2>/dev/null || true
truncate -s 0 /root/.python_history 2>/dev/null || true
history -c 2>/dev/null || true
echo "完成"; echo ""
# ── 清除 tpms log ─────────────────────────────────────────────────
echo "[7/10] 清除 tpms log 檔..."
rm -f /home/pi/vc01-rpi3/log/tpms_server*.log
echo "完成"; echo ""
# ── 清除 systemd journal logs ────────────────────────────────────
echo "[8/10] 清除 systemd journal logs..."
journalctl --rotate
journalctl --vacuum-time=1s
echo "完成"; echo ""

# ── 清除 /tmp ─────────────────────────────────────────────────────
echo "[9/10] 清除 /tmp..."
rm -rf /tmp/*
echo "完成"; echo ""

# ── 同步磁碟 ──────────────────────────────────────────────────────
echo "[10/10] 同步磁碟寫入..."
sync
echo "完成"; echo ""
echo "============================================"
echo "  清理完成！已準備好進行 dd 打包"
echo "============================================"
echo ""
echo "請執行關機後拔卡進行 dd："
echo "  sudo shutdown -h now"
echo ""
