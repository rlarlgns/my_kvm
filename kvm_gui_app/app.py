import pyperclip
import requests
import socket
from pynput import keyboard, mouse
import os
import sys
import json
import threading
import time
import struct

# Initialize pynput controllers
keyboard_controller = keyboard.Controller()
mouse_controller = mouse.Controller()

# --- Configuration ---
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200

# --- HID Code to pynput mappings ---
HID_CODE_TO_PYNPUT = {
    4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 
    14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 
    24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
    30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0',
    40: keyboard.Key.enter, 41: keyboard.Key.esc, 42: keyboard.Key.backspace, 43: keyboard.Key.tab, 44: keyboard.Key.space,
    79: keyboard.Key.right, 80: keyboard.Key.left, 81: keyboard.Key.down, 82: keyboard.Key.up
}

# --- State ---
my_id = "linux" if sys.platform.startswith('linux') else "mac"
last_clip = ""

def main_linux_console():
    """Main loop for Linux PC - Serial Only, Headless."""
    print(f"--- Starting Pi KVM Linux Client (Serial Mode) ---")
    print(f"Target Serial Port: {SERIAL_PORT}")
    
    import serial
    ser = None
    active_keys = set()
    global last_clip

    # Thread for local clipboard monitoring
    def clip_monitor():
        global last_clip
        while True:
            try:
                curr = pyperclip.paste()
                if curr and curr != last_clip:
                    if ser and ser.is_open:
                        payload = curr.encode('utf-8')
                        ser.write(b'\x03' + struct.pack('<H', len(payload)) + payload)
                        last_clip = curr
                        print(f"[Clipboard] Sent to Pi: {curr[:20]}...")
            except: pass
            time.sleep(2)
    
    threading.Thread(target=clip_monitor, daemon=True).start()

    while True:
        try:
            if not ser or not ser.is_open:
                if os.path.exists(SERIAL_PORT):
                    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
                    print(f"[Status] CONNECTED to Raspberry Pi via {SERIAL_PORT}")
                else:
                    print(f"[Status] Waiting for serial device {SERIAL_PORT}...", end='\r')
                    time.sleep(2)
                    continue

            # Send Heartbeat
            ser.write(b'\x04')

            header = ser.read(1)
            if not header: continue

            if header == b'\x01': # Keyboard
                report = ser.read(8)
                if len(report) == 8:
                    nk = {HID_CODE_TO_PYNPUT[report[i]] for i in range(2, 8) if report[i] in HID_CODE_TO_PYNPUT}
                    for k in nk - active_keys: keyboard_controller.press(k)
                    for k in active_keys - nk: keyboard_controller.release(k)
                    active_keys = nk
            
            elif header == b'\x02': # Mouse
                report = ser.read(4)
                if len(report) == 4:
                    _, dx, dy, s = struct.unpack('bbbb', report)
                    mouse_controller.move(dx, dy)
                    if s: mouse_controller.scroll(0, s)

            elif header == b'\x03': # Clipboard from Pi
                len_bytes = ser.read(2)
                if len(len_bytes) == 2:
                    c_len = struct.unpack('<H', len_bytes)[0]
                    c_data = ser.read(c_len).decode('utf-8', errors='ignore')
                    pyperclip.copy(c_data)
                    last_clip = c_data
                    print(f"[Clipboard] Received from Pi: {c_data[:20]}...")

        except Exception as e:
            print(f"\n[Error] Serial Communication: {e}")
            ser = None
            time.sleep(2)

def main_mac_gui():
    """Main loop for Mac - Network GUI."""
    import webview
    from flask import Flask, jsonify, request, send_from_directory
    
    app = Flask(__name__)
    app_state = { "pi_server_url": "http://192.168.42.2:5000", "my_id": "mac" }

    def resolve_path(p): return os.path.join(os.path.abspath(os.path.dirname(__file__)), p) if not getattr(sys, 'frozen', False) else os.path.join(sys._MEIPASS, p)
    
    @app.route('/')
    def index(): return send_from_directory(resolve_path('web'), 'index.html')
    @app.route('/<path:p>')
    def static_files(p): return send_from_directory(resolve_path('web'), p)

    @app.route('/api/status')
    def get_status():
        try:
            r = requests.get(f"{app_state['pi_server_url']}/status?id=mac", timeout=1.0)
            return jsonify(r.json())
        except: return jsonify({"server_status": "offline"})

    @app.route('/api/switch_target', methods=['POST'])
    def switch_target():
        t = request.get_json().get('target')
        requests.post(f"{app_state['pi_server_url']}/switch_target", json={"target": t}, timeout=1.0)
        return jsonify({"status": "success"})

    @app.route('/api/toggle_clipboard', methods=['POST'])
    def toggle_clipboard(): return jsonify({'status': 'success'})

    # Mac UDP Receiver Thread
    def mac_udp_worker():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: sock.bind(('0.0.0.0', 5002))
        except: return
        while True:
            try:
                data, _ = sock.recvfrom(1024)
                p = json.loads(data.decode())
                if p.get("type") == "keyboard":
                    # Input injection for Mac...
                    pass
            except: pass

    threading.Thread(target=mac_udp_worker, daemon=True).start()
    
    # Mac Clipboard Sync Thread
    def mac_clip_worker():
        lc = ""
        while True:
            try:
                cur = pyperclip.paste()
                if cur and cur != lc:
                    requests.post(f"{app_state['pi_server_url']}/clipboard", json={"content": cur, "source": "mac"}, timeout=1.0); lc = cur
                r = requests.get(f"{app_state['pi_server_url']}/clipboard", timeout=1.0)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("content") and d.get("source") == "linux" and d["content"] != lc:
                        pyperclip.copy(d["content"]); lc = d["content"]
            except: pass
            time.sleep(2)

    threading.Thread(target=mac_clip_worker, daemon=True).start()

    window = webview.create_window('Pi KVM Bridge', app, width=500, height=750)
    window.events.closed += lambda: os._exit(0)
    webview.start()

if __name__ == '__main__':
    if my_id == "linux":
        main_linux_console()
    else:
        main_mac_gui()
