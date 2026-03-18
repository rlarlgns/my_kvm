# pi_kvm_bridge/pi_input_forwarder.py
import asyncio
from evdev import InputDevice, categorize, ecodes, util
import requests, json, os, sys

HID_SERVER_URL = "http://127.0.0.1:5000"
TOGGLE_KEYS = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFTCTRL, ecodes.KEY_F12}

pressed_keys = set()
seen_devices = set()

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
        requests.post(f"{HID_SERVER_URL}/input", json=payload, timeout=0.1)
    except: pass

async def handle_keyboard_events(device):
    print(f"Monitoring Keyboard: {device.name} ({device.path})")
    async for event in device.async_read_loop():
        if event.type != ecodes.EV_KEY: continue
        key_event = categorize(event)
        
        scancode = key_event.scancode
        is_down = key_event.keystate == 1
        is_repeat = key_event.keystate == 2
        is_up = key_event.keystate == 0
        
        # Deduplication and Toggle logic
        if is_down:
            if scancode in pressed_keys: continue
            pressed_keys.add(scancode)
            if TOGGLE_KEYS.issubset(pressed_keys):
                print("Toggle Target Triggered!")
                requests.post(f"{HID_SERVER_URL}/switch_target", json={"target": "toggle"})
                pressed_keys.clear()
                continue
        elif is_up:
            if scancode not in pressed_keys: continue
            pressed_keys.discard(scancode)
        
        # Send press for both 1 (initial) and 2 (repeat)
        hid_key = EVDEV_KEY_TO_HID_SERVER_KEY_MAP.get(scancode)
        if hid_key:
            action = "press" if (is_down or is_repeat) else "release"
            send_to_hid_server({
                "type": "keyboard",
                "keys": [hid_key],
                "action": action
            })

async def handle_mouse_events(device):
    print(f"Monitoring Mouse: {device.name} ({device.path})")
    async for event in device.async_read_loop():
        payload = {"type": "mouse"}
        if event.type == ecodes.EV_REL:
            if event.code == ecodes.REL_X: payload["dx"] = event.value
            elif event.code == ecodes.REL_Y: payload["dy"] = event.value
            elif event.code == ecodes.REL_WHEEL: payload["scroll"] = -event.value
        elif event.type == ecodes.EV_KEY:
            btn = EVDEV_MOUSE_BUTTON_TO_STRING_MAP.get(event.code)
            if btn:
                payload["buttons"] = [btn]
                payload["action"] = "press" if event.value == 1 else "release"
        if len(payload) > 1: send_to_hid_server(payload)

async def find_devices():
    print("Scanning for input devices...")
    while True:
        for path in util.list_devices():
            if path in seen_devices: continue
            try:
                dev = InputDevice(path)
                caps = dev.capabilities()
                is_k = ecodes.EV_KEY in caps and len(caps[ecodes.EV_KEY]) > 10
                is_m = ecodes.EV_REL in caps and ecodes.REL_X in caps[ecodes.EV_REL]
                if is_k:
                    print(f"[*] Found Keyboard: {dev.name} at {dev.path}")
                    asyncio.create_task(handle_keyboard_events(dev))
                    seen_devices.add(path)
                elif is_m:
                    print(f"[*] Found Mouse: {dev.name} at {dev.path}")
                    asyncio.create_task(handle_mouse_events(dev))
                    seen_devices.add(path)
            except: pass
        await asyncio.sleep(2)

if __name__ == "__main__":
    print("--- Pi Input Forwarder Started (with Repeats) ---")
    try: asyncio.run(find_devices())
    except KeyboardInterrupt: pass
