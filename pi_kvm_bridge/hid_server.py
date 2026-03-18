# pi_kvm_bridge/hid_server.py
from flask import Flask, request, jsonify
import json, socket, struct, time, sys, os, threading
from threading import Lock

# Logging setup
LOG_FILE = "/tmp/pi_kvm.log"
def log_msg(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{ts}] {msg}"
    print(full_msg, file=sys.stderr)
    try:
        with open(LOG_FILE, "a") as f: f.write(full_msg + "\n")
    except: pass

try:
    import serial
except ImportError:
    serial = None

from hid_report_codes import KEY_MAP, MODIFIER_MAP, MOUSE_BUTTON_MAP, ASCII_TO_HID

app = Flask(__name__)

# --- Configuration ---
LINUX_KEYBOARD_GADGET_PATH = '/dev/hidg0'
LINUX_MOUSE_GADGET_PATH = '/dev/hidg1'
MAC_CLIENT_IP = '192.168.42.1'
MAC_CLIENT_PORT = 5002 
SERIAL_BAUDRATE = 115200

# --- Global State ---
state = {
    "kvm_target": "mac",
    "clipboard_content": "",
    "last_clipboard_source": None,
    "last_mac_seen": 0,
    "last_linux_seen": 0,
    "serial_port_path": None
}
state_lock = Lock()
serial_conn = None

def get_serial_connection():
    global serial_conn
    if not serial: return None
    with state_lock:
        if serial_conn and serial_conn.is_open: return serial_conn
        potential_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']
        for p in potential_ports:
            if os.path.exists(p):
                try:
                    serial_conn = serial.Serial(p, SERIAL_BAUDRATE, timeout=0.05)
                    state["serial_port_path"] = p
                    log_msg(f"Connected to Serial Port: {p}")
                    return serial_conn
                except Exception as e:
                    log_msg(f"Failed to open {p}: {e}")
        return None

def serial_reader_thread():
    global serial_conn
    while True:
        ser = get_serial_connection()
        if not ser:
            time.sleep(2); continue
        try:
            if ser.in_waiting:
                header = ser.read(1)
                if header == b'\x04': # Heartbeat
                    with state_lock: state["last_linux_seen"] = time.time()
                elif header == b'\x03': # Clipboard
                    len_bytes = ser.read(2)
                    if len(len_bytes) == 2:
                        clip_len = struct.unpack('<H', len_bytes)[0]
                        clip_data = ser.read(clip_len).decode('utf-8', errors='ignore')
                        with state_lock:
                            state["clipboard_content"] = clip_data
                            state["last_clipboard_source"] = "linux"
                        log_msg(f"Received clipboard from Linux ({clip_len} bytes)")
            else: time.sleep(0.05)
        except Exception as e:
            log_msg(f"Serial Reader Error: {e}")
            serial_conn = None; time.sleep(1)

@app.route('/status', methods=['GET'])
def get_status():
    client_id = request.args.get('id')
    with state_lock:
        now = time.time()
        if client_id == 'mac': state["last_mac_seen"] = now
        mac_connected = (now - state["last_mac_seen"]) < 10
        linux_connected = (now - state["last_linux_seen"]) < 10
        return jsonify({
            "kvm_target": state["kvm_target"],
            "server_status": "online",
            "mac_connected": mac_connected,
            "linux_connected": linux_connected,
            "serial_port": state["serial_port_path"]
        })

@app.route('/input', methods=['POST'])
def handle_input():
    data = request.get_json()
    input_type, action = data.get("type"), data.get("action")
    with state_lock: target = state["kvm_target"]
    if target == 'linux':
        ser = get_serial_connection()
        if input_type == "keyboard":
            modifiers = sum(MODIFIER_MAP.get(k.upper(), 0) for k in data.get("keys", []))
            keycodes = [KEY_MAP.get(k.upper(), 0) for k in data.get("keys", []) if k.upper() not in MODIFIER_MAP]
            report = bytearray(8); report[0] = modifiers
            for i in range(min(len(keycodes), 6)): report[i+2] = keycodes[i]
            if action == "release": report = bytearray(8)
            if ser:
                try: ser.write(b'\x01' + report)
                except: pass
        # Mouse logic same...
    elif target == 'mac':
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(json.dumps(data).encode(), (MAC_CLIENT_IP, MAC_CLIENT_PORT))
        except: pass
    return jsonify({"status": "success"})

@app.route('/debug/log')
def get_log():
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            return Response("".join(lines[-50:]), mimetype='text/plain')
    except: return "No log file found."

@app.route('/switch_target', methods=['POST'])
def switch_target():
    new_target = request.get_json().get("target")
    with state_lock:
        if new_target == "toggle": state["kvm_target"] = "linux" if state["kvm_target"] == "mac" else "mac"
        elif new_target in ["linux", "mac"]: state["kvm_target"] = new_target
        log_msg(f"Target switched to: {state['kvm_target']}")
    return jsonify({"status": "success", "target": state["kvm_target"]})

if __name__ == '__main__':
    log_msg("--- HID Server Starting ---")
    threading.Thread(target=serial_reader_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
