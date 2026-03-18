# device_checker.py
import os
from evdev import InputDevice, ecodes

print("--- Checking Input Device Capabilities ---")

# Path to the input devices
dev_input_path = "/dev/input/"

# List all potential event devices
event_devices = [os.path.join(dev_input_path, f) for f in os.listdir(dev_input_path) if f.startswith('event')] 

if not event_devices:
    print("No event devices found in /dev/input/")
else:
    for device_path in sorted(event_devices):
        try:
            device = InputDevice(device_path)
            print(f"\n--- Device: {device_path} ---")
            print(f"Name: {device.name}")
            print("Capabilities:")
            for cap_type, cap_codes in device.capabilities(verbose=True).items():
                cap_name = ecodes.EV[cap_type]
                print(f"  - {cap_name}:")
                # Don't print all keys if it's a huge list
                if cap_name == 'EV_KEY' and len(cap_codes) > 20:
                     print(f"    - Numerous keys ({len(cap_codes)} total)")
                     if ecodes.KEY_A in cap_codes:
                         print("    - (Contains KEY_A)")
                     if ecodes.KEY_LEFTSHIFT in cap_codes:
                         print("    - (Contains KEY_LEFTSHIFT)")
                else:
                    # To keep it simple, just print the number of codes
                    print(f"    - ({len(cap_codes)} codes)")


        except Exception as e:
            print(f"\n--- Could not inspect {device_path}: {e} ---")

print("\n--- Check Complete ---")
