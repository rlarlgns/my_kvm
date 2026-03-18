import os, sys, json, threading, time, struct, socket

# Mapping for common keys
HID_MAP = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z', 30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 40: 'enter', 41: 'esc', 42: 'backspace', 43: 'tab', 44: 'space', 79: 'right', 80: 'left', 81: 'down', 82: 'up'}

def run_linux_node():
    """Lightweight Linux Node - No GUI libs imported here."""
    print("\n--- PI KVM LINUX NODE (PURE SERIAL) ---")
    import serial, pyperclip
    from pynput import keyboard, mouse
    
    kb_ctrl, ms_ctrl = keyboard.Controller(), mouse.Controller()
    # Map string names to pynput keys
    KB_MAP = {'enter': keyboard.Key.enter, 'esc': keyboard.Key.esc, 'backspace': keyboard.Key.backspace, 'tab': keyboard.Key.tab, 'space': keyboard.Key.space, 'right': keyboard.Key.right, 'left': keyboard.Key.left, 'down': keyboard.Key.down, 'up': keyboard.Key.up}
    
    ser, active_keys, last_clip = None, set(), ""
    port = "/dev/ttyUSB0"

    def clip_mon():
        nonlocal last_clip
        while True:
            try:
                curr = pyperclip.paste()
                if curr and curr != last_clip and ser and ser.is_open:
                    pb = curr.encode('utf-8')
                    ser.write(b'\x03' + struct.pack('<H', len(pb)) + pb); ser.flush()
                    last_clip = curr
                    print(f"Sent Clipboard: {curr[:20]}...")
            except: pass
            time.sleep(2)
    
    threading.Thread(target=clip_mon, daemon=True).start()

    while True:
        try:
            if not ser or not ser.is_open:
                if os.path.exists(port):
                    ser = serial.Serial(port, 115200, timeout=0.1)
                    print(f"CONNECTED: {port}")
                else:
                    print(f"Waiting for {port}...", end='\r')
                    time.sleep(2); continue

            ser.write(b'\x04'); ser.flush() # Heartbeat
            h = ser.read(1)
            if not h: continue

            print(f"Raw Byte: {h.hex()}", end=' ') # DEBUG
            
            if h == b'\x01': # Keyboard
                r = ser.read(8)
                if len(r) == 8:
                    nk = set()
                    for i in range(2, 8):
                        if r[i] in HID_MAP:
                            val = HID_MAP[r[i]]
                            nk.add(KB_MAP.get(val, val))
                    for k in nk - active_keys: kb_ctrl.press(k)
                    for k in active_keys - nk: kb_ctrl.release(k)
                    active_keys = nk
            elif h == b'\x02': # Mouse
                r = ser.read(4)
                if len(r) == 4:
                    _, dx, dy, s = struct.unpack('bbbb', r)
                    ms_ctrl.move(dx, dy)
                    if s: ms_ctrl.scroll(0, s)
            elif h == b'\x03': # Clipboard
                lb = ser.read(2)
                if len(lb) == 2:
                    cl = struct.unpack('<H', lb)[0]
                    cd = ser.read(cl).decode('utf-8', errors='ignore')
                    pyperclip.copy(cd); last_clip = cd
                    print(f"Received Clipboard: {cd[:20]}...")
        except Exception as e:
            print(f"Error: {e}"); ser = None; time.sleep(2)

def run_mac_node():
    """Mac Node with GUI and Network."""
    import requests, paramiko, webview
    from flask import Flask, jsonify, request, Response, send_from_directory
    from pynput import keyboard, mouse
    import pyperclip
    
    app = Flask(__name__)
    PI_URL = "http://192.168.42.2:5000"
    kb_ctrl, ms_ctrl = keyboard.Controller(), mouse.Controller()
    
    # Mac specific mappings...
    MAC_KB_MAP = {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g', 'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n', 'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u', 'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '0': '0', 'ENTER': keyboard.Key.enter, 'SPACE': keyboard.Key.space, 'BACKSPACE': keyboard.Key.backspace, 'TAB': keyboard.Key.tab, 'ESCAPE': keyboard.Key.esc, 'UP': keyboard.Key.up, 'DOWN': keyboard.Key.down, 'LEFT': keyboard.Key.left, 'RIGHT': keyboard.Key.right, 'LEFT_SHIFT': keyboard.Key.shift_l, 'LEFT_CTRL': keyboard.Key.ctrl_l, 'LEFT_GUI': keyboard.Key.cmd}

    @app.route('/')
    def index(): return send_from_directory(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'web'), 'index.html')
    @app.route('/api/status')
    def get_status():
        try: return jsonify(requests.get(f"{PI_URL}/status?id=mac", timeout=1.0).json())
        except: return jsonify({"server_status": "offline"})
    @app.route('/api/switch_target', methods=['POST'])
    def switch_target():
        requests.post(f"{PI_URL}/switch_target", json=request.get_json(), timeout=1.0)
        return jsonify({"status": "success"})
    @app.route('/api/deploy', methods=['POST'])
    def deploy():
        d = request.get_json()
        def gen():
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(d['ip'], username=d['user'], password=d['password'], timeout=10)
                yield "Deploying...\n"
                ssh.exec_command("sudo fuser -k 5000/tcp || true")
                ssh.exec_command(f"nohup /home/{d['user']}/pi_kvm_bridge/venv/bin/python /home/{d['user']}/pi_kvm_bridge/hid_server.py > /tmp/pi_kvm.log 2>&1 &")
                yield "Done.\n"
            except Exception as e: yield str(e)
            finally: ssh.close()
        return Response(gen(), mimetype='text/plain')

    def udp_worker():
        sock, pressed = socket.socket(socket.AF_INET, socket.SOCK_DGRAM), set()
        sock.bind(('0.0.0.0', 5002))
        while True:
            try:
                data, _ = sock.recvfrom(1024)
                p = json.loads(data.decode())
                if p.get("type") == "keyboard":
                    for ks in p.get("keys", []):
                        pk = MAC_KB_MAP.get(ks)
                        if pk:
                            if p.get("action") == "press" and pk not in pressed: kb_ctrl.press(pk); pressed.add(pk)
                            elif p.get("action") == "release" and pk in pressed: kb_ctrl.release(pk); pressed.discard(pk)
                elif p.get("type") == "mouse":
                    dx, dy, s = p.get("dx", 0), p.get("dy", 0), p.get("scroll", 0)
                    ms_ctrl.move(dx, dy)
                    if s: ms_ctrl.scroll(0, s)
            except: pass

    threading.Thread(target=udp_worker, daemon=True).start()
    webview.start(webview.create_window('Pi KVM Bridge', app, width=500, height=750))

if __name__ == '__main__':
    if sys.platform.startswith('linux'):
        run_linux_node()
    else:
        run_mac_node()
