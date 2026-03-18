#!/bin/bash
set -e

echo "--- KVM Bridge GUI 빌드 스크립트 ---"

# 앱 이름을 지정합니다.
APP_NAME="PiKVM"
APP_SCRIPT="kvm_gui_app/app.py"

echo "이전 빌드 파일들을 정리합니다..."
rm -rf build/ dist/ "${APP_NAME}.spec"

echo "PyInstaller 빌드를 시작합니다..."

pyinstaller --noconsole \
            --onefile \
            --name "${APP_NAME}" \
            --hidden-import=webview \
            --hidden-import=paramiko \
            --add-data 'kvm_gui_app/web:web' \
            --add-data 'pi_kvm_bridge:pi_kvm_bridge' \
            --add-data 'setup_hid_gadget_linux.sh:.' \
            --add-data 'hid-gadget-setup.service:.' \
            --add-data 'pi-hid-server.service:.' \
            --add-data 'pi-input-forwarder.service:.' \
            --add-data 'setup_pi_scenario3.sh:.' \
            "${APP_SCRIPT}"

echo ""
echo "--- 빌드 완료! ---"
echo "실행 파일은 'dist/' 디렉토리에서 찾을 수 있습니다."
echo "macOS에서는 'dist/${APP_NAME}', 리눅스에서는 'dist/${APP_NAME}' 입니다."
echo "각 운영체제에 맞는 실행 파일을 만들려면 해당 OS에서 이 스크립트를 실행해야 합니다."