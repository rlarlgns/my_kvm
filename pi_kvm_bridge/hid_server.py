# pi_kvm_bridge/hid_server.py
from flask import Flask, request, jsonify
import json
import socket
import struct
import time
import sys
import os
from threading import Lock

# Optional: serial for Linux connection
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

# Import HID report codes
from hid_report_codes import KEY_MAP, MODIFIER_MAP, MOUSE_BUTTON_MAP, ASCII_TO_HID

app = Flask(__name__)

# --- Configuration ---
LINUX_KEYBOARD_GADGET_PATH = '/dev/hidg0'
LINUX_MOUSE_GADGET_PATH = '/dev/hidg1'
MAC_CLIENT_IP = '192.168.42.1'
MAC_CLIENT_PORT = 5002 
SERIAL_PORT = '/dev/ttyUSB0' 
SERIAL_BAUDRATE = 115200

# --- Global State ---
state = {
    "kvm_target": "mac",
    "clipboard_content": "",
    "last_clipboard_source": None,
    "last_mac_seen": 0,
    "last_linux_seen": 0
}
state_lock = Lock()
serial_conn = None

def get_serial_connection():
    global serial_conn
    if not serial: return None
    with state_lock:
        if serial_conn and serial_conn.is_open: return serial_conn
        try:
            if os.path.exists(SERIAL_PORT):
                serial_conn = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=0.1)
                return serial_conn
        except: pass
    return None

def check_serial_status():
    conn = get_serial_connection()
    return conn is not None and conn.is_open

def send_to_mac_client(data):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(data).encode(), (MAC_CLIENT_IP, MAC_CLIENT_PORT))
        return True
    except: return False

def generate_keyboard_report(modifiers, keycodes):
    report = bytearray(8)
    report[0] = modifiers
    for i in range(min(len(keycodes), 6)): report[i+2] = keycodes[i]
    return report

def generate_mouse_report(buttons, dx, dy, scroll):
    def to_signed_char(val): return struct.pack('b', max(-127, min(127, val)))[0]
    report = bytearray(4)
    report[0] = buttons
    report[1] = to_signed_char(dx)
    report[2] = to_signed_char(dy)
    report[3] = to_signed_char(scroll)
    return report

def write_to_hid_gadget(device_path, report_bytes):
    try:
        if os.path.exists(device_path):
            with open(device_path, 'wb') as f: f.write(report_bytes)
            return True
        return False
    except: return False

@app.route('/input', methods=['POST'])
def handle_input():
    data = request.get_json()
    input_type, action = data.get("type"), data.get("action")
    with state_lock: target = state["kvm_target"]

    if target == 'linux':
        ser = get_serial_connection()
        if input_type == "keyboard":
            if action == "release": report = generate_keyboard_report(0, [])
            else:
                modifiers = sum(MODIFIER_MAP.get(k.upper(), 0) for k in data.get("keys", []))
                keycodes = [KEY_MAP.get(k.upper(), 0) for k in data.get("keys", []) if k.upper() not in MODIFIER_MAP]
                report = generate_keyboard_report(modifiers, keycodes)
            write_to_hid_gadget(LINUX_KEYBOARD_GADGET_PATH, report)
            if ser:
                try: ser.write(b'\x01' + report)
                except: pass
        elif input_type == "mouse":
            if action == "release" and not data.get("dx") and not data.get("dy"):
                report = generate_mouse_report(0, 0, 0, 0)
            else:
                button_mask = sum(MOUSE_BUTTON_MAP.get(b.upper(), 0) for b in data.get("buttons", []))
                report = generate_mouse_report(button_mask, data.get("dx", 0), data.get("dy", 0), data.get("scroll", 0))
            write_to_hid_gadget(LINUX_MOUSE_GADGET_PATH, report)
            if ser:
                try: ser.write(b'\x02' + report)
                except: pass
    elif target == 'mac':
        send_to_mac_client(data)
    return jsonify({"status": "success"})

@app.route('/status', methods=['GET'])
def get_status():
    client_id = request.args.get('id')
    with state_lock:
        now = time.time()
        if client_id == 'mac': state["last_mac_seen"] = now
        elif client_id == 'linux': state["last_linux_seen"] = now
        
        mac_connected = (now - state["last_mac_seen"]) < 10
        linux_client_connected = (now - state["last_linux_seen"]) < 10
        linux_serial_connected = check_serial_status()
        
        return jsonify({
            "kvm_target": state["kvm_target"],
            "server_status": "online",
            "mac_connected": mac_connected,
            "linux_connected": linux_client_connected or linux_serial_connected,
            "clipboard_last_update": state["last_clipboard_source"]
        })

@app.route('/switch_target', methods=['POST'])
def switch_target():
    new_target = request.get_json().get("target")
    if new_target in ["linux", "mac"]:
        with state_lock: state["kvm_target"] = new_target
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/clipboard', methods=['GET', 'POST'])
def handle_clipboard():
    if request.method == 'POST':
        data = request.get_json()
        with state_lock:
            state["clipboard_content"] = data.get("content", "")
            state["last_clipboard_source"] = data.get("source")
        return jsonify({"status": "success"})
    else:
        with state_lock:
            return jsonify({"content": state.get("clipboard_content", ""), "source": state["last_clipboard_source"]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
