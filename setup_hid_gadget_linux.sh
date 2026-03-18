#!/bin/bash

GADGET_NAME="pi_kvm_linux"
GADGET_DIR="/sys/kernel/config/usb_gadget/${GADGET_NAME}"

# --- 1. Load modules (if not already loaded by cmdline.txt) ---
# modprobe libcomposite # This should ideally be handled by cmdline.txt
# modprobe dwc2 # This should ideally be handled by cmdline.txt

# --- 2. Create the gadget directory ---
if [ -d "${GADGET_DIR}" ]; then
    echo "Removing existing gadget directory ${GADGET_DIR}"
    rmdir ${GADGET_DIR}/functions/hid.usb0
    rmdir ${GADGET_DIR}/functions/hid.usb1
    rmdir ${GADGET_DIR}/configs/c.1/strings/0x409
    rmdir ${GADGET_DIR}/configs/c.1
    rmdir ${GADGET_DIR}/strings/0x409
    rmdir ${GADGET_DIR}
fi

echo "Creating gadget directory ${GADGET_DIR}"
mkdir -p ${GADGET_DIR} || { echo "Failed to create gadget directory"; exit 1; }
cd ${GADGET_DIR} || { echo "Failed to change to gadget directory"; exit 1; }

# --- 3. Set Vendor and Product IDs ---
echo "Setting Vendor and Product IDs"
echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice # v1.0.0
echo 0x0200 > bcdUSB    # USB 2.0

# --- 4. Create string descriptors ---
echo "Creating string descriptors"
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "Raspberry Pi" > strings/0x409/manufacturer
echo "Pi KVM Bridge (Linux)" > strings/0x409/product

# --- 5. Create a configuration ---
echo "Creating configuration c.1"
mkdir -p configs/c.1/strings/0x409
echo 120 > configs/c.1/MaxPower # MaxPower in mA
echo "Config 1: USB HID KVM" > configs/c.1/strings/0x409/configuration

# --- 6. Create HID functions ---

# Keyboard HID Function (hid.usb0)
echo "Creating keyboard HID function (hid.usb0)"
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol     # Keyboard
echo 1 > functions/hid.usb0/subclass    # Boot Interface Subclass
echo 8 > functions/hid.usb0/report_length # Standard boot keyboard report (8 bytes)

# Standard Keyboard Report Descriptor (from hid-gadget.txt documentation)
# This descriptor matches a standard 8-byte boot keyboard report:
# Byte 0: Modifier keys (Ctrl, Shift, Alt, GUI)
# Bytes 1: Reserved (always 0)
# Bytes 2-7: Up to 6 key codes currently pressed
echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc

# Mouse HID Function (hid.usb1)
echo "Creating mouse HID function (hid.usb1)"
mkdir -p functions/hid.usb1
echo 2 > functions/hid.usb1/protocol     # Mouse
echo 0 > functions/hid.usb1/subclass    # No subclass
echo 4 > functions/hid.usb1/report_length # 4-byte report (buttons, dx, dy, scroll)

# Standard Mouse Report Descriptor (from hid-gadget.txt documentation)
# This descriptor matches a standard 4-byte boot mouse report:
# Byte 0: Buttons (Bit 0: Left, Bit 1: Right, Bit 2: Middle)
# Byte 1: X-axis movement (signed)
# Byte 2: Y-axis movement (signed)
# Byte 3: Wheel movement (signed)
echo -ne '\x05\x01\x09\x02\xa1\x01\x09\x01\xa1\x00\x05\x09\x19\x01\x29\x03\x15\x00\x25\x01\x95\x03\x75\x01\x81\x02\x95\x01\x75\x05\x81\x03\x05\x01\x09\x30\x09\x31\x09\x38\x15\x81\x25\x7f\x75\x08\x95\x03\x81\x06\xc0\xc0' > functions/hid.usb1/report_desc

# --- 7. Link functions to the configuration ---
echo "Linking HID functions to configuration c.1"
ln -s functions/hid.usb0 configs/c.1/
ln -s functions/hid.usb1 configs/c.1/

# --- 8. Enable the gadget by binding a UDC (USB Device Controller) ---
# Find the available UDC. On Raspberry Pi, it's typically "fe980000.usb" or "20980000.usb" depending on the model.
# For RPi400, it's generally "fe980000.usb".
UDC_CONTROLLER=$(ls /sys/class/udc | head -n 1) # Get the first available UDC
if [ -z "${UDC_CONTROLLER}" ]; then
    echo "No UDC controller found. Ensure dwc2 module is loaded and hardware is configured."
    exit 1
fi
echo "${UDC_CONTROLLER}" > UDC

echo "USB HID gadget for Linux PC is set up and active using UDC: ${UDC_CONTROLLER}"
echo "You should now see 'Pi KVM Bridge (Linux)' as a USB keyboard/mouse on your connected Linux PC."
echo "Check with 'lsusb' and 'dmesg' on the Linux PC."
