# pi_kvm_bridge/hid_server.py
from flask import Flask, request, jsonify, Response
import json, socket, struct, time, sys, os, threading
from threading import Lock

# Logging
LOG_FILE = "/tmp/pi_kvm.log"
def log_msg(msg):
    full_msg = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(full_msg, file=sys.stderr)
    try:
        with open(LOG_FILE, "a") as f: f.write(full_msg + "\n")
    except: pass

try: import serial
except: serial = None

from hid_report_codes import KEY_MAP, MODIFIER_MAP, MOUSE_BUTTON_MAP

app = Flask(__name__)
LINUX_KEYBOARD_GADGET_PATH = '/dev/hidg0'
LINUX_MOUSE_GADGET_PATH = '/dev/hidg1'
MAC_CLIENT_IP = '192.168.42.1'
MAC_CLIENT_PORT = 5002 
SERIAL_BAUDRATE = 115200

state = {"kvm_target": "mac", "clipboard_content": "", "last_mac_seen": 0, "last_linux_seen": 0, "serial_port": None}
state_lock = Lock()
serial_conn = None

def get_serial_connection():
    global serial_conn
    if not serial: return None
    with state_lock:
        if serial_conn and serial_conn.is_open: return serial_conn
        for p in ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyUSB1']:
            if os.path.exists(p):
                try:
                    serial_conn = serial.Serial(p, SERIAL_BAUDRATE, timeout=0.1)
                    state["serial_port"] = p
                    log_msg(f"SUCCESS: Opened Serial Port {p}")
                    return serial_conn
                except Exception as e: log_msg(f"ERROR: Could not open {p}: {e}")
        return None

def serial_reader():
    while True:
        ser = get_serial_connection()
        if not ser: time.sleep(2); continue
        try:
            if ser.in_waiting:
                h = ser.read(1)
                if h == b'\x04': # Heartbeat
                    with state_lock: state["last_linux_seen"] = time.time()
                elif h == b'\x03': # Clipboard
                    lb = ser.read(2)
                    if len(lb) == 2:
                        cl = struct.unpack('<H', lb)[0]
                        cd = ser.read(cl).decode('utf-8', errors='ignore')
                        with state_lock: state["clipboard_content"], state["last_clipboard_source"] = cd, "linux"
                        log_msg(f"Serial: Received clipboard ({cl} bytes)")
            else: time.sleep(0.01)
        except: time.sleep(1)

@app.route('/input', methods=['POST'])
def handle_input():
    data = request.get_json()
    with state_lock: target = state["kvm_target"]
    if target == 'linux':
        ser = get_serial_connection()
        if data.get("type") == "keyboard":
            modifiers = sum(MODIFIER_MAP.get(k.upper(), 0) for k in data.get("keys", []))
            keycodes = [KEY_MAP.get(k.upper(), 0) for k in data.get("keys", []) if k.upper() not in MODIFIER_MAP]
            report = bytearray(8); report[0] = modifiers
            for i in range(min(len(keycodes), 6)): report[i+2] = keycodes[i]
            if data.get("action") == "release": report = bytearray(8)
            if ser:
                try: ser.write(b'\x01' + report); ser.flush()
                except: pass
        # Mouse logic...
    elif target == 'mac':
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(json.dumps(data).encode(), (MAC_CLIENT_IP, MAC_CLIENT_PORT))
        except: pass
    return jsonify({"status": "success"})

@app.route('/status')
def get_status():
    cid = request.args.get('id')
    with state_lock:
        now = time.time()
        if cid == 'mac': state["last_mac_seen"] = now
        return jsonify({
            "kvm_target": state["kvm_target"],
            "mac_connected": (now - state["last_mac_seen"]) < 10,
            "linux_connected": (now - state["last_linux_seen"]) < 10,
            "serial_port": state["serial_port"]
        })

@app.route('/debug/log')
def get_log():
    try:
        with open(LOG_FILE, "r") as f: return Response("".join(f.readlines()[-50:]), mimetype='text/plain')
    except: return "No log."

@app.route('/switch_target', methods=['POST'])
def switch_target():
    t = request.get_json().get("target")
    with state_lock:
        if t == "toggle": state["kvm_target"] = "linux" if state["kvm_target"] == "mac" else "mac"
        else: state["kvm_target"] = t
    return jsonify({"status": "success", "target": state["kvm_target"]})

if __name__ == '__main__':
    log_msg("--- Pi KVM Server Started ---")
    threading.Thread(target=serial_reader, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
