# pi_kvm_bridge/device_checker.py
import os
from evdev import InputDevice, util

print("--- Checking Raspberry Pi Devices ---")

# 1. Check HID Input Devices
print("\n[Input Devices]")
devices = [InputDevice(path) for path in util.list_devices()]
if not devices:
    print("No input devices found.")
for device in devices:
    print(f"- {device.path}: {device.name}")

# 2. Check Serial Ports
print("\n[Serial Ports]")
serial_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']
found_serial = False
for p in serial_ports:
    if os.path.exists(p):
        print(f"- {p}: EXISTS")
        found_serial = True
if not found_serial:
    print("No common serial ports found.")

# 3. Check HID Gadgets (Targeting Linux via USB OTG)
print("\n[HID Gadgets]")
gadgets = ['/dev/hidg0', '/dev/hidg1']
for g in gadgets:
    status = "READY" if os.path.exists(g) else "NOT FOUND"
    print(f"- {g}: {status}")

print("\n--- Check Complete ---")
