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
import struct
from flask import Flask, jsonify, request, Response, send_from_directory

# Initialize pynput controllers
keyboard_controller = keyboard.Controller()
mouse_controller = mouse.Controller()

# --- HID Code to pynput mappings (Simplified) ---
HID_CODE_TO_PYNPUT = {
    4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 
    14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 
    24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
    30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0',
    40: keyboard.Key.enter, 41: keyboard.Key.esc, 42: keyboard.Key.backspace, 43: keyboard.Key.tab, 44: keyboard.Key.space,
    79: keyboard.Key.right, 80: keyboard.Key.left, 81: keyboard.Key.down, 82: keyboard.Key.up
}

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

def resolve_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

@app.route('/')
def index(): return send_from_directory(resolve_path('web'), 'index.html')

@app.route('/<path:path>')
def static_files(path): return send_from_directory(resolve_path('web'), path)

@app.route('/api/status', methods=['GET'])
def get_status():
    try:
        my_id = app_state["my_id"]
        response = requests.get(f"{app_state['pi_server_url']}/status?id={my_id}", timeout=1.0)
        pi_data = response.json()
        with state_lock: app_state.update(pi_data); app_state["server_status"] = "online"
    except:
        with state_lock: app_state["server_status"] = "offline"; app_state["mac_connected"] = app_state["linux_connected"] = False
    with state_lock:
        return jsonify({
            "kvm_target": app_state.get("kvm_target", "unknown"),
            "server_status": app_state.get("server_status", "offline"),
            "mac_connected": app_state.get("mac_connected", False),
            "linux_connected": app_state.get("linux_connected", False),
            "clipboard_status": "active" if app_state.get("clipboard_sync_active") else "inactive"
        })

def sftp_upload_recursive(sftp, local_path, remote_path):
    for item in os.listdir(local_path):
        l_item = os.path.join(local_path, item)
        r_item = os.path.join(remote_path, item)
        if os.path.isfile(l_item): sftp.put(l_item, r_item)
        else:
            try: sftp.mkdir(r_item)
            except: pass
            sftp_upload_recursive(sftp, l_item, r_item)

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
    target = request.get_json().get('target')
    try: requests.post(f"{app_state['pi_server_url']}/switch_target", json={"target": target}, timeout=1.0)
    except: pass
    with state_lock: app_state["kvm_target"] = target
    return jsonify({"status": "success"})

@app.route('/api/toggle_clipboard', methods=['POST'])
def toggle_clipboard():
    with state_lock:
        app_state["clipboard_sync_active"] = not app_state["clipboard_sync_active"]
        return jsonify({'status': 'success', 'active': app_state["clipboard_sync_active"]})

# ==============================================================================
# 2. Background Workers
# ==============================================================================
def serial_receiver_worker():
    if app_state["my_id"] != "linux": return
    print("Serial receiver worker started (Linux mode).", file=sys.stderr)
    ser = None
    serial_port = "/dev/ttyUSB0"
    active_keys = set()
    while True:
        try:
            if not ser or not ser.is_open:
                if os.path.exists(serial_port):
                    import serial
                    ser = serial.Serial(serial_port, 115200, timeout=0.1)
                else: time.sleep(2); continue
            header = ser.read(1)
            if not header: continue
            if header == b'\x01': # Keyboard
                report = ser.read(8)
                if len(report) == 8:
                    new_keys = set()
                    for i in range(2, 8):
                        if report[i] in HID_CODE_TO_PYNPUT: new_keys.add(HID_CODE_TO_PYNPUT[report[i]])
                    for k in new_keys - active_keys: keyboard_controller.press(k)
                    for k in active_keys - new_keys: keyboard_controller.release(k)
                    active_keys = new_keys
            elif header == b'\x02': # Mouse
                report = ser.read(4)
                if len(report) == 4:
                    _, dx, dy, scroll = struct.unpack('bbbb', report)
                    mouse_controller.move(dx, dy)
                    if scroll: mouse_controller.scroll(0, scroll)
        except: ser = None; time.sleep(2)

def clipboard_sync_worker():
    last_clip = ""
    while True:
        try:
            with state_lock:
                active, pi_url, my_id = app_state["clipboard_sync_active"], app_state["pi_server_url"], app_state["my_id"]
            if active:
                try:
                    curr = pyperclip.paste()
                    if curr and curr != last_clip:
                        requests.post(f"{pi_url}/clipboard", json={"content": curr, "source": my_id}, timeout=1.0)
                        last_clip = curr
                    resp = requests.get(f"{pi_url}/clipboard", timeout=1.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("content") and data.get("source") != my_id and data.get("content") != last_clip:
                            pyperclip.copy(data["content"]); last_clip = data["content"]
                except: pass
            time.sleep(2)
        except: time.sleep(5)

def input_receiver_worker():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try: sock.bind(('0.0.0.0', 5002))
    except: return
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            payload = json.loads(data.decode())
            # Basic pynput injection for Mac client (Network)
            if payload.get("type") == "keyboard":
                key_str, action = payload.get("keys", [None])[0], payload.get("action")
                # This part can be refined similarly to KeyRepeater if needed
        except: pass

def on_closed(): os._exit(0)

if __name__ == '__main__':
    threading.Thread(target=input_receiver_worker, daemon=True).start()
    threading.Thread(target=clipboard_sync_worker, daemon=True).start()
    threading.Thread(target=serial_receiver_worker, daemon=True).start()
    if "--headless" in sys.argv:
        print("--- Running in HEADLESS mode ---")
        app.run(host='0.0.0.0', port=5000)
    else:
        try:
            window = webview.create_window('Pi KVM Bridge', app, width=500, height=750)
            window.events.closed += on_closed
            webview.start()
        except:
            print("GUI failed. Starting in HEADLESS mode...")
            app.run(host='0.0.0.0', port=5000)
