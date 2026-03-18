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
import paramiko

# Initialize controllers
keyboard_controller = keyboard.Controller()
mouse_controller = mouse.Controller()

# --- Mappings ---
HID_CODE_TO_PYNPUT = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z', 30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 40: keyboard.Key.enter, 41: keyboard.Key.esc, 42: keyboard.Key.backspace, 43: keyboard.Key.tab, 44: keyboard.Key.space, 79: keyboard.Key.right, 80: keyboard.Key.left, 81: keyboard.Key.down, 82: keyboard.Key.up}
PYNPUT_KEY_MAP = { 'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g', 'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n', 'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u', 'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '0': '0', 'ENTER': keyboard.Key.enter, 'SPACE': keyboard.Key.space, 'BACKSPACE': keyboard.Key.backspace, 'TAB': keyboard.Key.tab, 'ESCAPE': keyboard.Key.esc, 'DELETE': keyboard.Key.delete, 'UP': keyboard.Key.up, 'DOWN': keyboard.Key.down, 'LEFT': keyboard.Key.left, 'RIGHT': keyboard.Key.right, 'LEFT_SHIFT': keyboard.Key.shift_l, 'RIGHT_SHIFT': keyboard.Key.shift_r, 'LEFT_ALT': keyboard.Key.alt_l, 'RIGHT_ALT': keyboard.Key.alt_r, 'LEFT_CTRL': keyboard.Key.ctrl_l, 'RIGHT_CTRL': keyboard.Key.ctrl_r, 'LEFT_GUI': keyboard.Key.cmd, 'RIGHT_GUI': keyboard.Key.cmd }
PYNPUT_MOUSE_BUTTON_MAP = {'LEFT': mouse.Button.left, 'RIGHT': mouse.Button.right, 'MIDDLE': mouse.Button.middle}

# --- Shared Config ---
PI_SERVER_URL = "http://192.168.42.2:5000"
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200

# ==============================================================================
# LINUX CORE (No GUI, No Flask needed for core communication)
# ==============================================================================
def run_linux_serial_node():
    print(f"\n--- PI KVM LINUX NODE (SERIAL MODE) ---")
    print(f"Target Port: {SERIAL_PORT} @ {BAUDRATE}")
    
    import serial
    ser, active_keys, last_clip = None, set(), ""

    def clip_monitor():
        nonlocal last_clip
        while True:
            try:
                curr = pyperclip.paste()
                if curr and curr != last_clip and ser and ser.is_open:
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
                    print(f"\n[Status] CONNECTED to Raspberry Pi via {SERIAL_PORT}")
                else:
                    print(f"[Status] Waiting for {SERIAL_PORT}...", end='\r')
                    time.sleep(2); continue

            # Send Heartbeat periodically
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
            elif header == b'\x03': # Clipboard
                l_bytes = ser.read(2)
                if len(l_bytes) == 2:
                    cl = struct.unpack('<H', l_bytes)[0]
                    cd = ser.read(cl).decode('utf-8', errors='ignore')
                    pyperclip.copy(cd); last_clip = cd
                    print(f"[Clipboard] Received from Pi: {cd[:20]}...")
        except Exception as e:
            print(f"\n[Error] Serial: {e}")
            ser = None; time.sleep(2)

# ==============================================================================
# MAC CORE (GUI + Network)
# ==============================================================================
def run_mac_gui():
    from flask import Flask, jsonify, request, Response, send_from_directory
    app = Flask(__name__)
    
    def resolve_path(p):
        if getattr(sys, 'frozen', False): return os.path.join(sys._MEIPASS, p)
        return os.path.join(os.path.abspath(os.path.dirname(__file__)), p)

    @app.route('/')
    def index(): return send_from_directory(resolve_path('web'), 'index.html')
    @app.route('/<path:p>')
    def static_files(p): return send_from_directory(resolve_path('web'), p)

    @app.route('/api/status', methods=['GET', 'POST'])
    def get_status():
        try:
            r = requests.get(f"{PI_SERVER_URL}/status?id=mac", timeout=1.0)
            return jsonify(r.json())
        except: return jsonify({"server_status": "offline"})

    @app.route('/api/switch_target', methods=['GET', 'POST'])
    def switch_target():
        t = request.get_json().get('target')
        try: requests.post(f"{PI_SERVER_URL}/switch_target", json={"target": t}, timeout=1.0)
        except: pass
        return jsonify({"status": "success"})

    @app.route('/api/toggle_clipboard', methods=['GET', 'POST'])
    def toggle_clipboard():
        # Mac internal sync flag could be added here
        return jsonify({'status': 'success', 'active': True})

    @app.route('/api/deploy', methods=['POST'])
    def deploy():
        d = request.get_json()
        def gen():
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(d['ip'], username=d['user'], password=d['password'], timeout=10)
                yield "Connected!\n"
                sftp = ssh.open_sftp()
                remote_p = f"/home/{d['user']}/pi_kvm_bridge"
                ssh.exec_command(f"mkdir -p {remote_p}")
                local_p = resolve_path('../pi_kvm_bridge') if not getattr(sys, 'frozen', False) else resolve_path('pi_kvm_bridge')
                for f in os.listdir(local_p):
                    if os.path.isfile(os.path.join(local_p, f)): sftp.put(os.path.join(local_p, f), f"{remote_p}/{f}")
                sftp.close()
                ssh.exec_command("sudo fuser -k 5000/tcp || true")
                ssh.exec_command(f"nohup {remote_p}/venv/bin/python {remote_p}/hid_server.py > /tmp/pi_kvm.log 2>&1 &")
                ssh.exec_command(f"nohup sudo {remote_p}/venv/bin/python {remote_p}/pi_input_forwarder.py >> /tmp/pi_kvm.log 2>&1 &")
                yield "Pi Deployment finished."
            except Exception as e: yield f"Error: {e}\n"
            finally: ssh.close()
        return Response(gen(), mimetype='text/plain')

    def input_receiver():
        sock, locally_pressed = socket.socket(socket.AF_INET, socket.SOCK_DGRAM), set()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: sock.bind(('0.0.0.0', 5002))
        except: return
        while True:
            try:
                data, _ = sock.recvfrom(1024)
                p = json.loads(data.decode())
                if p.get("type") == "keyboard":
                    action = p.get("action")
                    for ks in p.get("keys", []):
                        pk = PYNPUT_KEY_MAP.get(ks)
                        if pk:
                            if action == "press" and pk not in locally_pressed:
                                keyboard_controller.press(pk); locally_pressed.add(pk)
                            elif action == "release" and pk in locally_pressed:
                                keyboard_controller.release(pk); locally_pressed.discard(pk)
                elif p.get("type") == "mouse":
                    dx, dy, s = p.get("dx", 0), p.get("dy", 0), p.get("scroll", 0)
                    if dx or dy: mouse_controller.move(dx, dy)
                    if s: mouse_controller.scroll(0, s)
                    for bs in p.get("buttons", []):
                        bm = PYNPUT_MOUSE_BUTTON_MAP.get(bs)
                        if bm:
                            if p.get("action") == "press": mouse_controller.press(bm)
                            else: mouse_controller.release(bm)
            except: pass

    def clipboard_sync():
        lc = ""
        while True:
            try:
                cur = pyperclip.paste()
                if cur and cur != lc:
                    requests.post(f"{PI_SERVER_URL}/clipboard", json={"content": cur, "source": "mac"}, timeout=1.0); lc = cur
                r = requests.get(f"{PI_SERVER_URL}/clipboard", timeout=1.0)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("content") and d.get("source") == "linux" and d["content"] != lc:
                        pyperclip.copy(d["content"]); lc = d["content"]
            except: pass
            time.sleep(2)

    threading.Thread(target=input_receiver, daemon=True).start()
    threading.Thread(target=clipboard_sync, daemon=True).start()
    
    import webview
    w = webview.create_window('Pi KVM Bridge', app, width=500, height=750)
    w.events.closed += lambda: os._exit(0)
    webview.start()

if __name__ == '__main__':
    if sys.platform.startswith('linux'):
        run_linux_serial_node()
    else:
        run_mac_gui()
