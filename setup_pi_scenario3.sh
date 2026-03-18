#!/bin/bash
set -e

# This script is intended to be run on the Raspberry Pi.
# It sets up all necessary components for Scenario 3.

# --- Variables ---
PROJECT_SOURCE_DIR="/home/pi/pi-kvm-bridge"
PROJECT_INSTALL_DIR="/opt/pi-kvm-bridge"

echo "--- Starting Scenario 3 Setup on Raspberry Pi ---"

if [ "$EUID" -ne 0 ]; then
  echo "ERROR: This script must be run as root (sudo)."
  exit 1
fi

# --- 1. Initial OS Configuration ---
echo "Step 1: Configuring /boot/config.txt and /boot/cmdline.txt..."
# (Logic remains the same)
if ! grep -q "dtoverlay=dwc2" /boot/config.txt; then
    echo "Adding dtoverlay=dwc2 to /boot/config.txt"
    echo -e "\n# Enable dwc2 for USB gadget mode\ndtoverlay=dwc2" >> /boot/config.txt
fi
if ! grep -q "modules-load=dwc2,libcomposite" /boot/cmdline.txt; then
    echo "Adding modules-load=dwc2,libcomposite to /boot/cmdline.txt"
    sed -i 's/$/ modules-load=dwc2,libcomposite/' /boot/cmdline.txt
fi

# --- 2. Install Dependencies ---
echo "Step 2: Installing system packages and Python dependencies..."
apt-get update
apt-get install -y python3-pip python3-dev
pip3 install -r "${PROJECT_SOURCE_DIR}/pi_kvm_bridge/requirements.txt"

# --- 3. Deploy Project Files ---
echo "Step 3: Deploying project files to ${PROJECT_INSTALL_DIR}..."
mkdir -p "${PROJECT_INSTALL_DIR}"
rsync -a --delete "${PROJECT_SOURCE_DIR}/pi_kvm_bridge/" "${PROJECT_INSTALL_DIR}/pi_kvm_bridge/"
rsync -a --delete "${PROJECT_SOURCE_DIR}/setup_hid_gadget_linux.sh" "${PROJECT_INSTALL_DIR}/"
chmod +x "${PROJECT_INSTALL_DIR}/setup_hid_gadget_linux.sh"

# --- 4. Configure and Enable Systemd Services (IMPROVED) ---
echo "Step 4: Setting up systemd services..."

SERVICE_FILES=(
    "hid-gadget-setup.service"
    "pi-hid-server.service"
    "pi-input-forwarder.service"
)
ALL_SERVICES_FOUND=true

for service_file in "${SERVICE_FILES[@]}"; do
    SOURCE_PATH="${PROJECT_SOURCE_DIR}/${service_file}"
    DEST_PATH="/etc/systemd/system/${service_file}"
    if [ -f "${SOURCE_PATH}" ]; then
        echo "Copying ${service_file} to ${DEST_PATH}..."
        cp "${SOURCE_PATH}" "${DEST_PATH}"
    else
        echo "FATAL ERROR: Service file ${SOURCE_PATH} not found! This file was not deployed correctly from the Mac GUI."
        ALL_SERVICES_FOUND=false
    fi
done

if [ "$ALL_SERVICES_FOUND" = false ]; then
    echo "One or more service files were missing. Aborting setup."
    exit 1
fi

echo "Reloading systemd and enabling services..."
systemctl daemon-reload
systemctl enable hid-gadget-setup.service
systemctl enable pi-hid-server.service
systemctl enable pi-input-forwarder.service

echo "Systemd services enabled."

# --- Final Instructions ---
echo "--- Raspberry Pi Setup for Scenario 3 is Complete! ---"
echo "A reboot is required to apply the OS configuration changes."
echo "You can reboot now by typing: sudo reboot"