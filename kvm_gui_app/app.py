import os, sys, json, threading, time, struct, socket, paramiko
import requests, webview, pyperclip
from flask import Flask, jsonify, request, Response, send_from_directory
from pynput import keyboard, mouse

# Initialize controllers
keyboard_controller = keyboard.Controller()
mouse_controller = mouse.Controller()

# --- Configuration ---
config = {
    "PI_URL": "http://192.168.42.2:5000",
    "MAC_UDP_PORT": 5002,
    "SERIAL_BAUDRATE": 115200
}

# --- Mappings ---
HID_MAP = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z', 30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 40: 'enter', 41: 'esc', 42: 'backspace', 43: 'tab', 44: 'space', 79: 'right', 80: 'left', 81: 'down', 82: 'up'}
MAC_KB_MAP = {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g', 'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n', 'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u', 'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '0': '0', 'ENTER': keyboard.Key.enter, 'SPACE': keyboard.Key.space, 'BACKSPACE': keyboard.Key.backspace, 'TAB': keyboard.Key.tab, 'ESCAPE': keyboard.Key.esc, 'UP': keyboard.Key.up, 'DOWN': keyboard.Key.down, 'LEFT': keyboard.Key.left, 'RIGHT': keyboard.Key.right, 'LEFT_SHIFT': keyboard.Key.shift_l, 'LEFT_CTRL': keyboard.Key.ctrl_l, 'LEFT_GUI': keyboard.Key.cmd}
PYNPUT_MOUSE_BUTTON_MAP = {'LEFT': mouse.Button.left, 'RIGHT': mouse.Button.right, 'MIDDLE': mouse.Button.middle}

# --- Path Helper ---
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ==============================================================================
# MAC GUI NODE
# ==============================================================================
def run_mac_node():
    # Set web folder path explicitly
    web_dir = get_resource_path('web')
    app = Flask(__name__, static_folder=web_dir, template_folder=web_dir)
    app.deploy_running = False
    
    @app.route('/')
    def index(): return send_from_directory(web_dir, 'index.html')
    @app.route('/<path:p>')
    def static_files(p): return send_from_directory(web_dir, p)

    @app.route('/api/status')
    def get_status():
        try: return jsonify(requests.get(f"{config['PI_URL']}/status?id=mac", timeout=1.0).json())
        except: return jsonify({"server_status": "offline"})

    @app.route('/api/switch_target', methods=['POST'])
    def switch_target():
        try: requests.post(f"{config['PI_URL']}/switch_target", json=request.get_json(), timeout=1.0)
        except: pass
        return jsonify({"status": "success"})

    @app.route('/api/toggle_clipboard', methods=['POST'])
    def toggle_clipboard():
        return jsonify({"status": "success"})

    @app.route('/api/run_checker', methods=['POST'])
    def run_checker():
        d = request.get_json()
        def gen():
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(d['ip'], username=d['user'], password=d['password'], timeout=10)
                remote_root = f"/home/{d['user']}/pi_kvm_bridge"
                cmd = f"test -f {remote_root}/venv/bin/python && {remote_root}/venv/bin/python {remote_root}/pi_kvm_bridge/device_checker.py || python3 {remote_root}/pi_kvm_bridge/device_checker.py"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                for line in stdout: yield line
                for line in stderr: yield line
            except Exception as e: yield f"Error: {e}\n"
            finally: ssh.close()
        return Response(gen(), mimetype='text/plain')

    @app.route('/api/deploy', methods=['POST'])
    def deploy():
        if app.deploy_running:
            return Response("Another deployment is already in progress...\n", mimetype='text/plain')
            
        d = request.get_json()
        global config
        config['PI_URL'] = f"http://{d['ip']}:5000"
        
        def gen():
            app.deploy_running = True
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(d['ip'], username=d['user'], password=d['password'], timeout=10)
                yield "--- Connected to Pi ---\n"
                
                yield "Nuclear Cleanup: Killing all existing KVM processes...\n"
                cleanup_cmd = (
                    "sudo systemctl stop pi-hid-server pi-input-forwarder || true; "
                    "sudo systemctl disable pi-hid-server pi-input-forwarder || true; "
                    "sudo pkill -9 -f pi_kvm_bridge || true; "
                    "sudo pkill -9 -f hid_server.py || true; "
                    "sudo pkill -9 -f pi_input_forwarder.py || true; "
                    "sudo fuser -k 5000/tcp || true; "
                    "sleep 1"
                )
                _, stdout, _ = ssh.exec_command(cleanup_cmd)
                stdout.channel.recv_exit_status()
                
                stdin, stdout, stderr = ssh.exec_command("ps aux | grep pi_kvm_bridge | grep -v grep || echo 'Clean'")
                cleanup_status = stdout.read().decode().strip()
                yield f"Cleanup Status: {cleanup_status if cleanup_status else 'All processes terminated.'}\n"

                curr_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(curr_dir)
                local_src = os.path.join(project_root, 'pi_kvm_bridge')
                if getattr(sys, 'frozen', False):
                    local_src = os.path.join(sys._MEIPASS, 'pi_kvm_bridge')

                remote_root = f"/home/{d['user']}/pi_kvm_bridge"
                remote_src = f"{remote_root}/pi_kvm_bridge"
                
                yield "Cleaning old files...\n"
                _, stdout, _ = ssh.exec_command(f"rm -rf {remote_root} && mkdir -p {remote_src}")
                stdout.channel.recv_exit_status()
                
                sftp = ssh.open_sftp()
                for f in os.listdir(local_src):
                    l_file = os.path.join(local_src, f)
                    if os.path.isfile(l_file):
                        yield f"Uploading {f} to pi_kvm_bridge/...\n"
                        sftp.put(l_file, f"{remote_src}/{f}")
                        if f == "requirements.txt":
                            sftp.put(l_file, f"{remote_root}/{f}")
                
                extra_files = ["hid-gadget-setup.service", "pi-hid-server.service", "pi-input-forwarder.service", "setup_hid_gadget_linux.sh"]
                for f in extra_files:
                    l_file = os.path.join(project_root, f)
                    if os.path.exists(l_file):
                        yield f"Uploading {f} to root...\n"
                        sftp.put(l_file, f"{remote_root}/{f}")
                sftp.close()
                
                yield "Creating venv (this may take a few seconds)...\n"
                _, stdout, _ = ssh.exec_command(f"python3 -m venv {remote_root}/venv")
                stdout.channel.recv_exit_status()
                
                python_path, pip_path = f"{remote_root}/venv/bin/python", f"{remote_root}/venv/bin/pip"
                
                yield "Installing dependencies (pip install)...\n"
                cmd = f"{pip_path} install --upgrade pip && {pip_path} install -r {remote_root}/requirements.txt"
                _, stdout, stderr = ssh.exec_command(cmd)
                if stdout.channel.recv_exit_status() == 0:
                    yield "Dependencies installed successfully.\n"
                else:
                    yield f"Pip install error: {stderr.read().decode()}\n"
                
                yield "Restarting components...\n"
                ssh.exec_command("sudo rm /tmp/pi_hid_server.log /tmp/pi_forwarder.log || true")
                ssh.exec_command(f"sudo nohup {python_path} {remote_src}/hid_server.py > /tmp/pi_hid_server.log 2>&1 &")
                yield "HID Server started.\n"
                time.sleep(2)
                ssh.exec_command(f"sudo nohup {python_path} {remote_src}/pi_input_forwarder.py > /tmp/pi_forwarder.log 2>&1 &")
                yield "Input Forwarder started.\n"
                yield "\n--- DEPLOYMENT FINISHED ---\n"
                yield "All processes are fresh and running.\n"
                
            except Exception as e: yield f"Deploy Error: {e}\n"
            finally: 
                ssh.close()
                app.deploy_running = False
        return Response(gen(), mimetype='text/plain')

    def udp_worker():
        sock, pressed = socket.socket(socket.AF_INET, socket.SOCK_DGRAM), set()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: 
            sock.bind(('0.0.0.0', config['MAC_UDP_PORT']))
            print(f"[*] Mac UDP Listener started on port {config['MAC_UDP_PORT']}")
        except: return
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                p = json.loads(data.decode())
                print(f"[UDP] Received: {p}")
                if p.get("type") == "keyboard":
                    for ks in p.get("keys", []):
                        pk = MAC_KB_MAP.get(ks)
                        if pk:
                            try:
                                if p.get("action") == "press" and pk not in pressed:
                                    keyboard_controller.press(pk); pressed.add(pk)
                                    print(f"[Key] Pressed {ks}")
                                elif p.get("action") == "release" and pk in pressed:
                                    keyboard_controller.release(pk); pressed.discard(pk)
                                    print(f"[Key] Released {ks}")
                            except: pass
                elif p.get("type") == "mouse":
                    dx, dy, s = p.get("dx", 0), p.get("dy", 0), p.get("scroll", 0)
                    mouse_controller.move(dx, dy)
                    if s: mouse_controller.scroll(0, s)
            except: pass

    threading.Thread(target=udp_worker, daemon=True).start()
    webview.create_window('Pi KVM Bridge', app, width=500, height=750)
    webview.start()

def run_linux_node():
    print("\n--- PI KVM LINUX NODE ---")
    import serial
    ser, active_keys = None, set()
    port = "/dev/ttyUSB0"
    KB_MAP = {'enter': keyboard.Key.enter, 'esc': keyboard.Key.esc, 'backspace': keyboard.Key.backspace, 'tab': keyboard.Key.tab, 'space': keyboard.Key.space, 'right': keyboard.Key.right, 'left': keyboard.Key.left, 'down': keyboard.Key.down, 'up': keyboard.Key.up}
    while True:
        try:
            if not ser or not ser.is_open:
                if os.path.exists(port):
                    ser = serial.Serial(port, config['SERIAL_BAUDRATE'], timeout=0.1)
                    print(f"CONNECTED: {port}")
                else: time.sleep(2); continue
            ser.write(b'\x04'); ser.flush() 
            h = ser.read(1)
            if h == b'\x01': 
                r = ser.read(8)
                if len(r) == 8:
                    nk = {HID_MAP[r[i]] for i in range(2, 8) if r[i] in HID_MAP}
                    mapped_nk = {KB_MAP.get(k, k) for k in nk}
                    for k in mapped_nk - active_keys: keyboard_controller.press(k)
                    for k in active_keys - mapped_nk: keyboard_controller.release(k)
                    active_keys = mapped_nk
            elif h == b'\x02': 
                r = ser.read(4)
                if len(r) == 4:
                    _, dx, dy, s = struct.unpack('bbbb', r)
                    mouse_controller.move(dx, dy)
                    if s: mouse_controller.scroll(0, s)
        except: ser = None; time.sleep(2)

if __name__ == '__main__':
    if sys.platform.startswith('linux'): run_linux_node()
    else: run_mac_node()
