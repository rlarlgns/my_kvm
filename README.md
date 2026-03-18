# Pi KVM Bridge GUI

A simple KVM solution that turns a Raspberry Pi into a bridge for controlling a Mac and a Linux PC using a single keyboard and mouse connected to the Pi. This version uses a graphical user interface (GUI) for easy control and deployment.

![KVM GUI Screenshot](https://i.imgur.com/your-screenshot-url.png) <!-- Placeholder -->

## Features

*   **GUI Control Panel:** An easy-to-use interface to manage all KVM functions.
*   **Scenario 3 Focused:** Uses the Raspberry Pi as the central input source to control other computers.
*   **Dual Control Methods:** Switch KVM targets via a GUI button or a keyboard hotkey (`Left Shift + Left Ctrl + F12`).
*   **Bidirectional Clipboard Sync:** Copy on your Mac, paste on your Linux PC, and vice-versa. Can be toggled on/off.
*   **Automated Pi Deployment:** A "Deploy" button in the Mac GUI automates the entire setup process on your Raspberry Pi.

## How It Works

The system consists of three main components:

1.  **The GUI App (Mac & Linux):** This is the control center (`kvm_gui_app/app.py`). You run it on both your Mac and Linux PC. It provides status information, control buttons, and handles clipboard synchronization for the local machine. The Mac version also includes the deployment module.
2.  **The Pi Server (Raspberry Pi):** A Flask server (`pi_kvm_bridge/hid_server.py`) that runs on the Pi. It receives commands from the GUI, manages the KVM target state, and serves as the central hub for clipboard content.
3.  **The Pi Input Forwarder (Raspberry Pi):** A script (`pi_kvm_bridge/pi_input_forwarder.py`) that captures input from the keyboard and mouse connected to the Pi and sends it to the Pi Server. It also detects the hotkey for switching targets.

---

## Setup and Usage

### Prerequisites

*   **Python 3:** Installed on your Mac, Linux PC, and Raspberry Pi.
*   **Git:** To clone this repository.
*   **On Mac:** [Homebrew](https://brew.sh/) for installing `cliclick`.
*   **On Linux:** `xclip` for clipboard access (`sudo apt install xclip`).
*   **On Raspberry Pi:** A fresh install of Raspberry Pi OS Lite (Bookworm recommended).

### Step 1: Get the Project

Clone this repository to your Mac.

```bash
git clone <repository_url>
cd <repository_name>
```

### Step 2: Run the App on Your Mac

1.  **Install Dependencies:**
    ```bash
    pip3 install -r kvm_gui_app/requirements.txt
    brew install cliclick
    ```

2.  **Run the Application:**
    ```bash
    python3 kvm_gui_app/app.py
    ```
    The GUI window should appear.

### Step 3: Deploy to Raspberry Pi

1.  In the GUI application on your Mac, find the **"Deploy to Pi"** section.
2.  Enter the IP Address, User, and Password for your Raspberry Pi.
3.  Click the **Deploy** button.
4.  The log window will show the progress of files being copied and the remote setup script being executed.
5.  Once the log shows "DEPLOYMENT FINISHED", **reboot your Raspberry Pi** as instructed. You can do this from the Mac terminal: `ssh pi@<pi_ip> 'sudo reboot'`.

### Step 4: Run the App on Your Linux PC

1.  **Manually Copy Project Folder:** Copy the entire project folder from your Mac to your Linux PC (e.g., using `scp`, a USB drive, or a shared network folder).
    ```bash
    # Example from your Linux PC, copying from your Mac
    scp -r your_mac_user@your_mac_ip:/path/to/project_folder ~/
    ```

2.  **Install Dependencies:**
    ```bash
    cd /path/to/project_folder
    sudo apt update && sudo apt install -y python3-dev xclip
    pip3 install -r kvm_gui_app/requirements.txt
    ```

3.  **Run the Application:**
    ```bash
    python3 kvm_gui_app/app.py
    ```

### Step 5: Using the KVM

1.  Ensure the GUI app is running on both your Mac and Linux PC.
2.  After the Pi reboots, the server components will start automatically. The status light in the GUI should turn green.
3.  Use the keyboard and mouse connected to your Raspberry Pi. The input will be forwarded to the target machine shown in the GUI.
4.  **Switch Targets:** Click the "Switch Target" button in the GUI on either machine, or press `Left Shift + Left Ctrl + F12` on the Pi's keyboard.
5.  **Use Clipboard:** Click "Start Sync" in the GUI on both Mac and Linux. You can now copy text on one machine and paste it on the other.

## Troubleshooting

*   **Deployment Fails:**
    *   Check that you have `paramiko` installed (`pip show paramiko`).
    *   Verify the Pi's IP address, username, and password.
    *   Ensure SSH is enabled on the Raspberry Pi.
*   **GUI doesn't connect (Red Light):**
    *   Ensure the Pi has rebooted and is on the network.
    *   Verify the Pi's IP address and check that the `pi-hid-server` service is running on it (`systemctl status pi-hid-server`).
*   **Clipboard Sync Fails on Linux:**
    *   Make sure `xclip` is installed.
    *   The app must be run from a graphical session (not a text-only console), as it needs access to the display server's clipboard.
*   **Input Injection Fails on Mac:**
    *   Ensure you have granted **Accessibility Permissions** to your Terminal/IDE in `System Settings`.
