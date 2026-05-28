#!/usr/bin/env python3
"""
TPMS BLE Advertising Web Server
提供 REST API 給前端 Web UI 控制 BLE Advertising
需要 sudo 執行才能操作 HCI

安裝依賴：
  pip3 install flask flask-cors

執行：
  sudo python3 tpms_server.py
"""

import struct
import subprocess
import threading
import time
import sys
import json
import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
CORS(app)

# ── 設定檔路徑 ────────────────────────────────────────────────────────────────
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tpms_settings.json")
LOG_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
DEFAULT_PATTERN_TIRES = {
    "FL": {"pressure":2.1,"temperature":40,"voltage":3.0,"leak":False,"d2":"01","d3":"66","d4":"66","normal_interval":5,"normal_packet_count":5,"normal_packet_interval":20,"leak_packet_count":5,"leak_packet_interval":50,"active":True},
    "FR": {"pressure":2.1,"temperature":40,"voltage":3.0,"leak":False,"d2":"03","d3":"88","d4":"88","normal_interval":5,"normal_packet_count":5,"normal_packet_interval":20,"leak_packet_count":5,"leak_packet_interval":50,"active":True},
    "RL": {"pressure":2.1,"temperature":40,"voltage":3.0,"leak":False,"d2":"02","d3":"77","d4":"77","normal_interval":5,"normal_packet_count":5,"normal_packet_interval":20,"leak_packet_count":5,"leak_packet_interval":50,"active":True},
    "RR": {"pressure":2.1,"temperature":40,"voltage":3.0,"leak":False,"d2":"04","d3":"99","d4":"99","normal_interval":5,"normal_packet_count":5,"normal_packet_interval":20,"leak_packet_count":5,"leak_packet_interval":50,"active":True},
}


DEFAULT_TIRES = {
    "FR": {"pressure": 2.1, "temperature": 25.0, "voltage": 3.0, "leak": False, "active": True, "d2": "11", "d3": "22", "d4": "33", "normal_interval": 60, "normal_packet_count": 1, "normal_packet_interval": 50, "leak_packet_count": 5, "leak_packet_interval": 50},
    "RR": {"pressure": 2.1, "temperature": 25.0, "voltage": 3.0, "leak": False, "active": True, "d2": "44", "d3": "55", "d4": "66", "normal_interval": 60, "normal_packet_count": 1, "normal_packet_interval": 50, "leak_packet_count": 5, "leak_packet_interval": 50},
    "FL": {"pressure": 2.1, "temperature": 25.0, "voltage": 3.0, "leak": False, "active": True, "d2": "77", "d3": "88", "d4": "99", "normal_interval": 60, "normal_packet_count": 1, "normal_packet_interval": 50, "leak_packet_count": 5, "leak_packet_interval": 50},
    "RL": {"pressure": 2.1, "temperature": 25.0, "voltage": 3.0, "leak": False, "active": True, "d2": "AA", "d3": "BB", "d4": "CC", "normal_interval": 60, "normal_packet_count": 1, "normal_packet_interval": 50, "leak_packet_count": 5, "leak_packet_interval": 50},
}

def write_log(action, detail=""):
    try:
        ts = time.strftime("%Y/%m/%d %H:%M:%S")
        line = f"{ts}  {action}"
        if detail:
            line += f"  {detail}"
        ym = time.strftime("%Y%m")
        lp = os.path.join(LOG_DIR, f"tpms_server_{ym}.log")
        with open(lp, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
    except Exception as e:
        print(f"[WARN] log fail: {e}")

def load_settings():
    """從 JSON 檔案載入設定，若不存在則用預設值"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            # 合併：以預設值為底，覆蓋已儲存的值
            tires = {}
            for tid, defaults in DEFAULT_TIRES.items():
                tires[tid] = {**defaults, **saved.get("tires", {}).get(tid, {})}
            default_patterns = {str(i): {"name": f"Pattern {i}", "tires": None} for i in range(1,6)}
            saved_patterns = saved.get("patterns", {})
            patterns = {**default_patterns, **saved_patterns}
            return {
                "mode": saved.get("mode", "single"),
                "hci": saved.get("hci", "hci0"),
                "tires": tires,
                "patterns": patterns,
                "current_pattern": saved.get("current_pattern", None),
            }
        except Exception as e:
            print(f"[WARN] 讀取設定失敗，使用預設值：{e}")
    default_patterns = {str(i): {"name": f"Pattern {i}", "tires": None} for i in range(1,6)}
    return {"mode": "single", "hci": "hci0", "tires": {k: dict(v) for k, v in DEFAULT_TIRES.items()}, "patterns": default_patterns}

def save_settings():
    """將目前設定存入 JSON 檔案"""
    try:
        data = {
            "mode": advertising_state["mode"],
            "hci": HCI_DEV,
            "tires": advertising_state["tires"],
            "patterns": advertising_state["patterns"],
            "current_pattern": advertising_state["current_pattern"],
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] 儲存設定失敗：{e}")

# ── 全域狀態 ──────────────────────────────────────────────────────────────────
_saved = load_settings()
HCI_DEV = _saved["hci"]

advertising_state = {
    "running": False,
    "mode": _saved["mode"],
    "interval": 20,
    "tires": _saved["tires"],
    "current_tire": "FL",
    "last_payload": {},
    "log": [],
    "patterns": _saved.get("patterns", {str(i): {"name": f"Pattern {i}", "tires": None} for i in range(1,6)}),
    "current_pattern": _saved.get("current_pattern", None),
}

adv_threads = {}           # tire_id -> Thread
adv_stop_events = {}       # tire_id -> Event
hci_lock = threading.Lock()  # HCI 同時只能一顆輪胎使用

TIRE_POSITIONS = {
    "FL": 0x01,
    "RL": 0x02,
    "FR": 0x03,
    "RR": 0x04,
}

CUSTOM_MAC_SUFFIX = {
    "FR": [0x11, 0x22, 0x33],
    "RR": [0x44, 0x55, 0x66],
    "FL": [0x77, 0x88, 0x99],
    "RL": [0xAA, 0xBB, 0xCC],
}

# ── CRC16 ─────────────────────────────────────────────────────────────────────
def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x8005
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc

# ── Payload 組裝 ──────────────────────────────────────────────────────────────
def build_manufacturer_data(tire_id, tire_data):
    position = TIRE_POSITIONS[tire_id]
    d2 = int(tire_data.get("d2", "00"), 16) & 0xFF
    d3 = int(tire_data.get("d3", "00"), 16) & 0xFF
    d4 = int(tire_data.get("d4", "00"), 16) & 0xFF
    pressure_raw = int(tire_data["pressure"] * 100 / 3.13) & 0xFF
    temp_raw = int(tire_data["temperature"] + 50) & 0xFF
    voltage_raw = int((tire_data["voltage"] - 1.22) / 0.01) & 0xFF
    leak_byte = 0x01 if tire_data["leak"] else 0x00

    payload = bytes([
        0x68, 0x5A, 0x00,
        leak_byte, 0x80, 0x23,
        position,
        d2, d3, d4,
        pressure_raw, temp_raw, voltage_raw,
    ])
    crc = crc16(payload)
    return payload + bytes([(crc >> 8) & 0xFF, crc & 0xFF])

def build_adv_payload(mfr_data: bytes) -> bytes:
    flags = bytes([0x02, 0x01, 0x06])
    name_bytes = b"BY-N2"
    name = bytes([len(name_bytes) + 1, 0x09]) + name_bytes
    mfr = bytes([len(mfr_data) + 1, 0xFF]) + mfr_data
    return flags + name + mfr

# ── HCI 操作 ──────────────────────────────────────────────────────────────────
def hci_cmd(cmd_hex: str):
    cmd = f"hcitool -i {HCI_DEV} cmd {cmd_hex}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0

def set_adv_data(adv_payload: bytes):
    length = len(adv_payload)
    padded = adv_payload + bytes(31 - length)
    hex_str = " ".join(f"{b:02X}" for b in padded)
    return hci_cmd(f"0x08 0x0008 {length:02X} {hex_str}")

def set_adv_params(interval_ms: int = 100):
    interval = int(interval_ms / 0.625)
    lo = interval & 0xFF
    hi = (interval >> 8) & 0xFF
    return hci_cmd(f"0x08 0x0006 {lo:02X} {hi:02X} {lo:02X} {hi:02X} 03 00 00 00 00 00 00 00 07 00")

def set_adv_enable(enable: bool):
    return hci_cmd(f"0x08 0x000A {'01' if enable else '00'}")

def ensure_adv_ready():
    """確保 BlueZ 廣播模式已開啟，避免 hcitool 指令被 BlueZ 覆蓋"""
    subprocess.run(["btmgmt", "advertising", "on"], capture_output=True, timeout=5)

# ── 廣播邏輯 ──────────────────────────────────────────────────────────────────
def add_log(msg):
    advertising_state["log"].append({"time": time.strftime("%H:%M:%S"), "msg": msg})
    if len(advertising_state["log"]) > 50:
        advertising_state["log"].pop(0)

def do_advertise_single(tire_id):
    tire_data = advertising_state["tires"][tire_id]
    mfr = build_manufacturer_data(tire_id, tire_data)
    adv = build_adv_payload(mfr)
    crc = (mfr[13] << 8) | mfr[14]

    advertising_state["last_payload"][tire_id] = {
        "mfr_hex": mfr.hex(" ").upper(),
        "adv_hex": adv.hex(" ").upper(),
        "pressure_raw": mfr[10],
        "temp_raw": mfr[11],
        "voltage_raw": mfr[12],
        "crc": f"0x{crc:04X}",
    }

    set_adv_data(adv)
    set_adv_enable(True)
    add_log(f"[{tire_id}] 廣播中 | {tire_data['pressure']:.2f}Bar {tire_data['temperature']:.1f}C {tire_data['voltage']:.2f}V CRC={crc:04X}")

def tire_loop(tire_id, stop_event):
    """每顆輪胎獨立的廣播 Thread"""
    add_log(f"[{tire_id}] thread started")
    while not stop_event.is_set():
        tire_data = advertising_state["tires"][tire_id]
        is_leak = tire_data.get("leak", False)
        normal_interval = tire_data.get("normal_interval", 60)

        if not is_leak and normal_interval == 0:
            stop_event.wait(1)
            continue


        with hci_lock:
            send_tire_packets(tire_id, stop_event)

        if is_leak:
            # 漏氣模式：等待封包間隔後繼續發送
            wait_sec = tire_data.get("leak_packet_interval", 50) / 1000.0
        else:
            # 正常模式：等待 normal_interval 秒
            wait_sec = normal_interval

        stop_event.wait(wait_sec)

    add_log(f"[{tire_id}] thread stopped")


def send_tire_packets(tire_id, stop_event):
    """依照輪胎設定發送指定數量的封包"""
    tire_data = advertising_state["tires"][tire_id]
    is_leak = tire_data.get("leak", False)

    mfr = build_manufacturer_data(tire_id, tire_data)
    adv = build_adv_payload(mfr)
    crc = (mfr[13] << 8) | mfr[14]

    advertising_state["last_payload"][tire_id] = {
        "mfr_hex": mfr.hex(" ").upper(),
        "adv_hex": adv.hex(" ").upper(),
        "pressure_raw": mfr[10],
        "temp_raw": mfr[11],
        "voltage_raw": mfr[12],
        "crc": f"0x{crc:04X}",
    }
    advertising_state["current_tire"] = tire_id

    if is_leak:
        count = tire_data.get("leak_packet_count", 5)
        pkt_interval = tire_data.get("leak_packet_interval", 50) / 1000.0
    else:
        count = tire_data.get("normal_packet_count", 1)
        pkt_interval = tire_data.get("normal_packet_interval", 50) / 1000.0

    set_adv_params(50)
    set_adv_data(adv)
    for i in range(count):
        if stop_event.is_set():
            break
        set_adv_enable(True)
        stop_event.wait(pkt_interval)
        set_adv_enable(False)

    mode_str = "leak" if is_leak else "normal"
    add_log(f"[{tire_id}] {mode_str} | {tire_data['pressure']:.2f}Bar {tire_data['temperature']:.1f}C | {count}pkts interval={int(pkt_interval*1000)}ms | CRC={crc:04X}")


# ── API Routes ────────────────────────────────────────────────────────────────
@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "running": advertising_state["running"],
        "mode": advertising_state["mode"],
        "interval": advertising_state["interval"],
        "current_tire": advertising_state["current_tire"],
        "tires": advertising_state["tires"],
        "last_payload": advertising_state["last_payload"],
        "log": advertising_state["log"][-10:],
        "patterns": advertising_state["patterns"],
        "current_pattern": advertising_state["current_pattern"],
    })

@app.route("/api/tire/<tire_id>", methods=["POST"])
def update_tire(tire_id):
    if tire_id not in TIRE_POSITIONS:
        return jsonify({"error": "Invalid tire ID"}), 400
    data = request.json
    t = advertising_state["tires"][tire_id]
    changes = []
    def upd(key, cast, fmt=None):
        if key in data:
            ov = t.get(key)
            nv = cast(data[key])
            t[key] = nv
            if ov != nv:
                nl = fmt(nv) if fmt else str(nv)
                ol = fmt(ov) if fmt else str(ov)
                changes.append(f"{key}: {ol} -> {nl}")
    upd("pressure",    float, lambda v: f"{v:.2f} Bar")
    upd("temperature", float, lambda v: f"{v:.1f} C")
    upd("voltage",     float, lambda v: f"{v:.2f} V")
    upd("leak",        bool,  lambda v: "leak" if v else "normal")
    upd("active",      bool)
    upd("d2", str); upd("d3", str); upd("d4", str)
    upd("normal_interval",       int, lambda v: f"{v}s")
    upd("normal_packet_count",   int, lambda v: f"{v} pkt")
    upd("normal_packet_interval",int, lambda v: f"{v} ms")
    upd("leak_packet_count",     int, lambda v: f"{v} pkt")
    upd("leak_packet_interval",  int, lambda v: f"{v} ms")
    save_settings()
    if changes:
        write_log("Change", f"{tire_id}: " + ", ".join(changes))
    return jsonify({"ok": True, "tire": t})

@app.route("/api/start", methods=["POST"])
def start_advertising():
    global adv_threads, adv_stop_events
    data = request.json or {}
    advertising_state["mode"] = data.get("mode", "single")
    advertising_state["current_tire"] = data.get("tire", "FL")

    if advertising_state["running"]:
        return jsonify({"ok": False, "error": "Already running"})

    mode = advertising_state["mode"]
    tires_to_run = ["FL", "RL", "FR", "RR"] if mode == "all" else [advertising_state["current_tire"]]

    for tire_id in tires_to_run:
        stop_ev = threading.Event()
        adv_stop_events[tire_id] = stop_ev
        t = threading.Thread(target=tire_loop, args=(tire_id, stop_ev), daemon=True)
        adv_threads[tire_id] = t
        t.start()

    advertising_state["running"] = True
    add_log(f"start mode={mode} tires={tires_to_run}")
    write_log("Start", f"mode={mode} tires={tires_to_run}")
    return jsonify({"ok": True})

@app.route("/api/stop", methods=["POST"])
def stop_advertising():
    global adv_threads, adv_stop_events
    for tire_id, stop_ev in adv_stop_events.items():
        stop_ev.set()
    adv_threads.clear()
    adv_stop_events.clear()
    set_adv_enable(False)
    advertising_state["running"] = False
    add_log("all advertising stopped")
    write_log("Close", "all advertising stopped")
    return jsonify({"ok": True})

@app.route("/api/hci", methods=["POST"])
def set_hci():
    global HCI_DEV
    data = request.json or {}
    HCI_DEV = data.get("hci", "hci0")
    save_settings()
    return jsonify({"ok": True, "hci": HCI_DEV})


@app.route("/api/pattern/save/<int:num>", methods=["POST"])
def pattern_save(num):
    if num < 1 or num > 5:
        return jsonify({"error": "1~5"}), 400
    import copy
    key = str(num)
    advertising_state["patterns"][key] = {
        "name": f"Pattern {num}",
        "tires": copy.deepcopy(advertising_state["tires"]),
    }
    advertising_state["current_pattern"] = num
    save_settings()
    write_log("Change", f"Type {num}, save pattern")
    add_log(f"[Pattern {num}] saved")
    return jsonify({"ok": True})

@app.route("/api/pattern/load/<int:num>", methods=["POST"])
def pattern_load(num):
    if num < 1 or num > 5:
        return jsonify({"error": "1~5"}), 400
    import copy
    key = str(num)
    p = advertising_state["patterns"].get(key, {})
    if not p or not p.get("tires"):
        p = {"tires": copy.deepcopy(DEFAULT_PATTERN_TIRES)}
    advertising_state["tires"] = copy.deepcopy(p["tires"])
    advertising_state["current_pattern"] = num
    save_settings()
    write_log("Change", f"Type {num}, load pattern")
    add_log(f"[Pattern {num}] loaded")
    return jsonify({"ok": True, "tires": advertising_state["tires"]})

@app.route("/api/patterns", methods=["GET"])
def get_patterns():
    return jsonify(advertising_state["patterns"])


@app.route('/api/reset', methods=['POST'])
def reset_all():
    DEFAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tpms_settings_default.json')
    try:
        with open(DEFAULT_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        advertising_state['tires'] = d.get('tires', {})
        advertising_state['patterns'] = d.get('patterns', {str(i): {'name': f'Pattern {i}', 'tires': None} for i in range(1,6)})
        advertising_state['mode'] = d.get('mode', 'single')
        advertising_state['current_pattern'] = d.get('current_pattern', None)
        save_settings()
        write_log('Change', 'reset all from default')
        add_log('[Reset] all settings restored')
        return jsonify({'ok': True, 'tires': advertising_state['tires'], 'patterns': advertising_state['patterns']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/")
def index():
    return render_template("tpms_ui.html")


def auto_start_advertising():
    global adv_threads, adv_stop_events
    advertising_state["mode"] = "all"
    tires_to_run = ["FL", "RL", "FR", "RR"]
    for tire_id in tires_to_run:
        stop_ev = threading.Event()
        adv_stop_events[tire_id] = stop_ev
        t = threading.Thread(target=tire_loop, args=(tire_id, stop_ev), daemon=True)
        adv_threads[tire_id] = t
        t.start()
    advertising_state["running"] = True
    add_log("auto-start mode=all")
    write_log("Start", "auto-start mode=all")
    print("[AUTO] started mode=all")

if __name__ == "__main__":
    print("TPMS BLE Web Server 啟動中...")
    print("請用瀏覽器開啟 http://<Pi的IP>:8101")
    auto_start_advertising()
    app.run(host="0.0.0.0", port=8101, debug=False)
