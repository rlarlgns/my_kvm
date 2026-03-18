# pi_kvm_bridge/pi_input_forwarder.py
import asyncio
from evdev import InputDevice, categorize, ecodes, util
import requests
import json
import time
import os
import sys

# --- Configuration ---
HID_SERVER_URL = "http://127.0.0.1:5000"
TOGGLE_KEYS = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFTCTRL, ecodes.KEY_F12}

# --- State ---
pressed_keys = set()
current_target = "linux"

# --- Mappings ---
# (EVDEV_KEY_TO_HID_SERVER_KEY_MAP remains the same as before)
EVDEV_KEY_TO_HID_SERVER_KEY_MAP = {
    ecodes.KEY_A: 'A', ecodes.KEY_B: 'B', ecodes.KEY_C: 'C', ecodes.KEY_D: 'D', ecodes.KEY_E: 'E', ecodes.KEY_F: 'F', ecodes.KEY_G: 'G', ecodes.KEY_H: 'H', ecodes.KEY_I: 'I', ecodes.KEY_J: 'J', ecodes.KEY_K: 'K', ecodes.KEY_L: 'L', ecodes.KEY_M: 'M', ecodes.KEY_N: 'N', ecodes.KEY_O: 'O', ecodes.KEY_P: 'P', ecodes.KEY_Q: 'Q', ecodes.KEY_R: 'R', ecodes.KEY_S: 'S', ecodes.KEY_T: 'T', ecodes.KEY_U: 'U', ecodes.KEY_V: 'V', ecodes.KEY_W: 'W', ecodes.KEY_X: 'X', ecodes.KEY_Y: 'Y', ecodes.KEY_Z: 'Z',
    ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3', ecodes.KEY_4: '4', ecodes.KEY_5: '5', ecodes.KEY_6: '6', ecodes.KEY_7: '7', ecodes.KEY_8: '8', ecodes.KEY_9: '9', ecodes.KEY_0: '0',
    ecodes.KEY_LEFTSHIFT: 'LEFT_SHIFT', ecodes.KEY_RIGHTSHIFT: 'RIGHT_SHIFT', ecodes.KEY_LEFTALT: 'LEFT_ALT', ecodes.KEY_RIGHTALT: 'RIGHT_ALT', ecodes.KEY_LEFTCTRL: 'LEFT_CTRL', ecodes.KEY_RIGHTCTRL: 'RIGHT_CTRL', ecodes.KEY_LEFTMETA: 'LEFT_GUI', ecodes.KEY_RIGHTMETA: 'RIGHT_GUI',
    ecodes.KEY_ENTER: 'ENTER', ecodes.KEY_SPACE: 'SPACE', ecodes.KEY_BACKSPACE: 'BACKSPACE', ecodes.KEY_TAB: 'TAB', ecodes.KEY_ESC: 'ESCAPE', ecodes.KEY_DELETE: 'DELETE',
    ecodes.KEY_UP: 'UP', ecodes.KEY_DOWN: 'DOWN', ecodes.KEY_LEFT: 'LEFT', ecodes.KEY_RIGHT: 'RIGHT',
    ecodes.KEY_F1: 'F1', ecodes.KEY_F2: 'F2', ecodes.KEY_F3: 'F3', ecodes.KEY_F4: 'F4', ecodes.KEY_F5: 'F5', ecodes.KEY_F6: 'F6', ecodes.KEY_F7: 'F7', ecodes.KEY_F8: 'F8', ecodes.KEY_F9: 'F9', ecodes.KEY_F10: 'F10', ecodes.KEY_F11: 'F11', ecodes.KEY_F12: 'F12',
}
EVDEV_MOUSE_BUTTON_TO_STRING_MAP = { ecodes.BTN_LEFT: 'LEFT', ecodes.BTN_RIGHT: 'RIGHT', ecodes.BTN_MIDDLE: 'MIDDLE' }


def send_to_hid_server(payload):
    try:
        requests.post(f"{HID_SERVER_URL}/input", json=payload, timeout=0.5)
    except requests.RequestException:
        pass # Suppress errors for speed

def switch_target():
    global current_target
    current_target = "mac" if current_target == "linux" else "linux"
    try:
        requests.post(f"{HID_SERVER_URL}/target", json={"target": current_target}, timeout=1.0)
        print(f"--- Target switched to: {current_target.upper()} ---", flush=True)
    except requests.RequestException as e:
        print(f"Error switching target: {e}", file=sys.stderr)


async def handle_keyboard_events(device):
    async for event in device.async_read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        
        key_event = categorize(event)
        key_code = key_event.scancode
        
        if key_event.keystate == key_event.key_down:
            pressed_keys.add(key_code)
            if TOGGLE_KEYS.issubset(pressed_keys):
                switch_target()
                # To prevent hotkey from being sent to target, we can clear the set
                pressed_keys.clear() 
                continue
        elif key_event.keystate == key_event.key_up:
            pressed_keys.discard(key_code)

        hid_key = EVDEV_KEY_TO_HID_SERVER_KEY_MAP.get(key_code)
        if hid_key:
            payload = {
                "type": "keyboard",
                "keys": [hid_key],
                "action": "press" if key_event.keystate == key_event.key_down else "release"
            }
            send_to_hid_server(payload)

async def handle_mouse_events(device):
    async for event in device.async_read_loop():
        payload = {"type": "mouse"}
        if event.type == ecodes.EV_REL:
            if event.code == ecodes.REL_X: payload["dx"] = event.value
            elif event.code == ecodes.REL_Y: payload["dy"] = event.value
            elif event.code == ecodes.REL_WHEEL: payload["scroll"] = -event.value
        elif event.type == ecodes.EV_KEY:
            button = EVDEV_MOUSE_BUTTON_TO_STRING_MAP.get(event.code)
            if button:
                payload["buttons"] = [button]
                payload["action"] = "press" if event.value == 1 else "release"
        
        if len(payload) > 1:
            send_to_hid_server(payload)

async def find_and_monitor_devices():
    tasks = []
    seen_devices = set()
    print("Scanning for input devices...")
    while True:
        devices = [InputDevice(path) for path in util.list_devices() if path not in seen_devices]
        for device in devices:
            is_keyboard = ecodes.EV_KEY in device.capabilities() and ecodes.KEY_A in device.capabilities().get(ecodes.EV_KEY, set())
            is_mouse = ecodes.EV_REL in device.capabilities() and ecodes.REL_X in device.capabilities().get(ecodes.EV_REL, set())

            if is_keyboard:
                print(f"Monitoring Keyboard: {device.name}")
                tasks.append(asyncio.create_task(handle_keyboard_events(device)))
                seen_devices.add(device.path)
            if is_mouse:
                print(f"Monitoring Mouse: {device.name}")
                tasks.append(asyncio.create_task(handle_mouse_events(device)))
                seen_devices.add(device.path)
        
        if not tasks:
            print("No input devices found yet. Retrying in 5 seconds...", file=sys.stderr)

        await asyncio.sleep(5)


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Warning: This script should be run with root privileges for input device access.", file=sys.stderr)
    
    print("--- Starting Pi Internal Input Forwarder ---")
    print(f"Hotkey to toggle target: { {ecodes.KEY[k] for k in TOGGLE_KEYS} }")
    
    try:
        asyncio.run(find_and_monitor_devices())
    except KeyboardInterrupt:
        print("\nExiting.")