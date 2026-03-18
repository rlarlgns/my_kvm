import pyperclip
import webview
import paramiko
import requests
import socket
from pynput import keyboard, mouse
import os
import sys
import json
import threading
import time
from flask import Flask, jsonify, request, Response, send_from_directory

# Initialize pynput controllers
keyboard_controller = keyboard.Controller()
mouse_controller = mouse.Controller()

# --- Mappings from HID Server keys to pynput keys ---
PYNPUT_KEY_MAP = {
    'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g', 'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n', 'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u', 'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z',
    '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '0': '0',
    **({'ENTER': keyboard.Key.enter} if hasattr(keyboard.Key, 'enter') else {}),
    **({'SPACE': keyboard.Key.space} if hasattr(keyboard.Key, 'space') else {}),
    **({'BACKSPACE': keyboard.Key.backspace} if hasattr(keyboard.Key, 'backspace') else {}),
    **({'TAB': keyboard.Key.tab} if hasattr(keyboard.Key, 'tab') else {}),
    **({'ESCAPE': keyboard.Key.esc} if hasattr(keyboard.Key, 'esc') else {}),
    **({'DELETE': keyboard.Key.delete} if hasattr(keyboard.Key, 'delete') else {}),
    **({'UP': keyboard.Key.up} if hasattr(keyboard.Key, 'up') else {}),
    **({'DOWN': keyboard.Key.down} if hasattr(keyboard.Key, 'down') else {}),
    **({'LEFT': keyboard.Key.left} if hasattr(keyboard.Key, 'left') else {}),
    **({'RIGHT': keyboard.Key.right} if hasattr(keyboard.Key, 'right') else {}),
    **({'LEFT_SHIFT': keyboard.Key.shift_l} if hasattr(keyboard.Key, 'shift_l') else {}),
    **({'RIGHT_SHIFT': keyboard.Key.shift_r} if hasattr(keyboard.Key, 'shift_r') else {}),
    **({'LEFT_ALT': keyboard.Key.alt_l} if hasattr(keyboard.Key, 'alt_l') else {}),
    **({'RIGHT_ALT': keyboard.Key.alt_r} if hasattr(keyboard.Key, 'alt_r') else {}),
    **({'LEFT_CTRL': keyboard.Key.ctrl_l} if hasattr(keyboard.Key, 'ctrl_l') else {}),
    **({'RIGHT_CTRL': keyboard.Key.ctrl_r} if hasattr(keyboard.Key, 'ctrl_r') else {}),
    **({'LEFT_GUI': keyboard.Key.cmd} if hasattr(keyboard.Key, 'cmd') else {}), 
    **({'RIGHT_GUI': keyboard.Key.cmd} if hasattr(keyboard.Key, 'cmd') else {}), 
    **({'F1': keyboard.Key.f1} if hasattr(keyboard.Key, 'f1') else {}),
    **({'F2': keyboard.Key.f2} if hasattr(keyboard.Key, 'f2') else {}),
    **({'F3': keyboard.Key.f3} if hasattr(keyboard.Key, 'f3') else {}),
    **({'F4': keyboard.Key.f4} if hasattr(keyboard.Key, 'f4') else {}),
    **({'F5': keyboard.Key.f5} if hasattr(keyboard.Key, 'f5') else {}),
    **({'F6': keyboard.Key.f6} if hasattr(keyboard.Key, 'f6') else {}),
    **({'F7': keyboard.Key.f7} if hasattr(keyboard.Key, 'f7') else {}),
    **({'F8': keyboard.Key.f8} if hasattr(keyboard.Key, 'f8') else {}),
    **({'F9': keyboard.Key.f9} if hasattr(keyboard.Key, 'f9') else {}),
    **({'F10': keyboard.Key.f10} if hasattr(keyboard.Key, 'f10') else {}),
    **({'F11': keyboard.Key.f11} if hasattr(keyboard.Key, 'f11') else {}),
    **({'F12': keyboard.Key.f12} if hasattr(keyboard.Key, 'f12') else {}),
}

PYNPUT_MOUSE_BUTTON_MAP = {
    'LEFT': mouse.Button.left,
    'RIGHT': mouse.Button.right,
    'MIDDLE': mouse.Button.middle,
}

class KeyRepeater(threading.Thread):
    def __init__(self, key_to_repeat, keyboard_controller, initial_delay=0.5, repeat_delay=0.05):
        super().__init__(daemon=True)
        self.key_to_repeat = key_to_repeat
        self.keyboard_controller = keyboard_controller
        self.initial_delay = initial_delay
        self.repeat_delay = repeat_delay
        self._stop_event = threading.Event()

    def run(self):
        try:
            self.keyboard_controller.press(self.key_to_repeat)
            self.keyboard_controller.release(self.key_to_repeat)
            time.sleep(self.initial_delay)
            while not self._stop_event.is_set():
                self.keyboard_controller.press(self.key_to_repeat)
                self.keyboard_controller.release(self.key_to_repeat)
                time.sleep(self.repeat_delay)
        except: pass

    def stop(self):
        self._stop_event.set()

def resolve_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# ==============================================================================
# 1. Flask Server for Backend API
# ==============================================================================
app = Flask(__name__)
app_state = { 
    "pi_server_url": "http://192.168.42.2:5000", 
    "clipboard_sync_active": False,
    "last_synced_clipboard": "",
    "mac_connected": False,
    "linux_connected": False,
    "my_id": "linux" if sys.platform.startswith('linux') else "mac"
}
state_lock = threading.Lock()

@app.route('/')
def index():
    return send_from_directory(resolve_path('web'), 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(resolve_path('web'), path)

@app.route('/api/status', methods=['GET'])
def get_status():
    try:
        pi_url = app_state["pi_server_url"]
        my_id = app_state["my_id"]
        response = requests.get(f"{pi_url}/status?id={my_id}", timeout=1.0)
        pi_data = response.json()
        with state_lock:
            app_state.update(pi_data)
            app_state["server_status"] = "online"
    except Exception as e:
        with state_lock:
            app_state["server_status"] = "offline"
            app_state["mac_connected"] = False
            app_state["linux_connected"] = False
    
    with state_lock:
        return jsonify({
            "kvm_target": app_state.get("kvm_target", "unknown"),
            "server_status": app_state.get("server_status", "offline"),
            "mac_connected": app_state.get("mac_connected", False),
            "linux_connected": app_state.get("linux_connected", False),
            "clipboard_status": "active" if app_state.get("clipboard_sync_active") else "inactive",
            "connection_error": app_state.get("connection_error", None)
        })

def sftp_upload_recursive(sftp, local_path, remote_path):
    for item in os.listdir(local_path):
        local_item_path = os.path.join(local_path, item)
        remote_item_path = os.path.join(remote_path, item)
        if os.path.isfile(local_item_path):
            sftp.put(local_item_path, remote_item_path)
        else:
            try: sftp.mkdir(remote_item_path)
            except: pass
            sftp_upload_recursive(sftp, local_item_path, remote_item_path)

@app.route('/api/deploy', methods=['POST'])
def deploy():
    data = request.get_json()
    pi_ip, pi_user, pi_pass = data.get('ip'), data.get('user'), data.get('password')
    def generate_logs():
        ssh = None
        try:
            yield f"Connecting to Pi at {pi_ip}...\\n"
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(pi_ip, username=pi_user, password=pi_pass, timeout=10)
            yield "Connection successful!\\n"
            sftp = ssh.open_sftp()
            yield "Uploading files...\\n"
            local_path = resolve_path('pi_kvm_bridge') if getattr(sys, 'frozen', False) else resolve_path('../pi_kvm_bridge')
            remote_path = f'/home/{pi_user}/pi_kvm_bridge'
            try: sftp.mkdir(remote_path)
            except: pass
            sftp_upload_recursive(sftp, local_path, remote_path)
            sftp.close()
            yield "Installing dependencies...\\n"
            venv_path = f"{remote_path}/venv"
            ssh.exec_command(f"python3 -m venv {venv_path} && {venv_path}/bin/pip install -r {remote_path}/requirements.txt")
            yield "Starting services...\\n"
            ssh.exec_command("sudo pkill -9 -f 'hid_server.py'; sudo pkill -9 -f 'pi_input_forwarder.py'")
            ssh.exec_command(f"nohup {venv_path}/bin/python {remote_path}/hid_server.py > /dev/null 2>&1 &")
            ssh.exec_command(f"nohup sudo {venv_path}/bin/python {remote_path}/pi_input_forwarder.py > /dev/null 2>&1 &")
            yield "Deployment finished."
        except Exception as e: yield f"Error: {str(e)}\\n"
        finally:
            if ssh: ssh.close()
    return Response(generate_logs(), mimetype='text/plain')

@app.route('/api/run_checker', methods=['POST'])
def run_checker():
    data = request.get_json()
    pi_ip, pi_user, pi_pass = data.get('ip'), data.get('user'), data.get('password')
    def generate_logs():
        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(pi_ip, username=pi_user, password=pi_pass, timeout=10)
            stdin, stdout, stderr = ssh.exec_command(f"sudo /home/{pi_user}/pi_kvm_bridge/venv/bin/python /home/{pi_user}/pi_kvm_bridge/device_checker.py")
            for line in iter(stdout.readline, ""): yield line
        except Exception as e: yield f"Error: {str(e)}\\n"
        finally:
            if ssh: ssh.close()
    return Response(generate_logs(), mimetype='text/plain')

@app.route('/api/switch_target', methods=['POST'])
def switch_target():
    try:
        pi_url = app_state["pi_server_url"]
        target = request.get_json().get('target')
        requests.post(f"{pi_url}/switch_target", json={"target": target}, timeout=1.0)
        with state_lock: app_state["kvm_target"] = target
        return jsonify({"status": "success", "new_target": target})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/toggle_clipboard', methods=['POST'])
def toggle_clipboard():
    with state_lock:
        app_state["clipboard_sync_active"] = not app_state["clipboard_sync_active"]
        active = app_state["clipboard_sync_active"]
    return jsonify({'status': 'success', 'active': active})

# ==============================================================================
# 2. Background Workers
# ==============================================================================
def serial_receiver_worker():
    if app_state["my_id"] != "linux": return
    print("Serial receiver worker started (Linux mode).", file=sys.stderr)
    ser = None
    serial_port = "/dev/ttyUSB0"
    while True:
        try:
            if not ser or not ser.is_open:
                if os.path.exists(serial_port):
                    import serial
                    ser = serial.Serial(serial_port, 115200, timeout=1.0)
                else: time.sleep(5); continue
            header = ser.read(1)
            if not header: continue
            if header == b'\x01': ser.read(8)
            elif header == b'\x02': ser.read(4)
        except: ser = None; time.sleep(5)

def clipboard_sync_worker():
    print("Clipboard sync worker started.", file=sys.stderr)
    last_local_clip = ""
    while True:
        try:
            with state_lock:
                active = app_state.get("clipboard_sync_active", False)
                pi_url = app_state["pi_server_url"]
                my_id = app_state["my_id"]
            if active:
                try:
                    current_local_clip = pyperclip.paste()
                    if current_local_clip and current_local_clip != last_local_clip:
                        requests.post(f"{pi_url}/clipboard", json={"content": current_local_clip, "source": my_id}, timeout=1.0)
                        last_local_clip = current_local_clip
                except: pass
                try:
                    resp = requests.get(f"{pi_url}/clipboard", timeout=1.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        remote_clip, remote_source = data.get("content", ""), data.get("source")
                        if remote_clip and remote_source != my_id and remote_clip != last_local_clip:
                            pyperclip.copy(remote_clip)
                            last_local_clip = remote_clip
                except: pass
            time.sleep(2)
        except: time.sleep(5)

def input_receiver_worker():
    listen_port = 5002
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    active_key_repeaters = {}
    try:
        sock.bind(('0.0.0.0', listen_port))
        print(f"UDP input receiver listening on port {listen_port}", file=sys.stderr)
    except: return
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            payload = json.loads(data.decode())
            input_type = payload.get("type")
            if input_type == "keyboard":
                keys, action = payload.get("keys", []), payload.get("action")
                for key_str in keys:
                    pynput_key = PYNPUT_KEY_MAP.get(key_str)
                    if pynput_key:
                        if action == "press":
                            if pynput_key not in active_key_repeaters:
                                repeater = KeyRepeater(pynput_key, keyboard_controller)
                                repeater.start(); active_key_repeaters[pynput_key] = repeater
                        elif action == "release":
                            if pynput_key in active_key_repeaters:
                                active_key_repeaters[pynput_key].stop(); del active_key_repeaters[pynput_key]
            elif input_type == "mouse":
                dx, dy, scroll = payload.get("dx", 0), payload.get("dy", 0), payload.get("scroll", 0)
                buttons, action = payload.get("buttons", []), payload.get("action")
                if dx != 0 or dy != 0: mouse_controller.move(dx, dy)
                if scroll != 0: mouse_controller.scroll(0, scroll)
                for btn_str in buttons:
                    pynput_button = PYNPUT_MOUSE_BUTTON_MAP.get(btn_str)
                    if pynput_button:
                        if action == "press": mouse_controller.press(pynput_button)
                        elif action == "release": mouse_controller.release(pynput_button)
        except: pass

def on_closed():
    os._exit(0)

if __name__ == '__main__':
    threading.Thread(target=input_receiver_worker, daemon=True).start()
    threading.Thread(target=clipboard_sync_worker, daemon=True).start()
    threading.Thread(target=serial_receiver_worker, daemon=True).start()
    window = webview.create_window('Pi KVM Bridge', app, width=500, height=750, resizable=False)
    window.events.closed += on_closed
    webview.start(debug=False)
