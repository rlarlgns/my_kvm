# Pi KVM 브리지 GUI

라즈베리 파이에 연결된 단일 키보드와 마우스를 사용하여 Mac과 리눅스 PC를 제어할 수 있도록 변환해주는 간단한 KVM 솔루션입니다. 이 버전은 쉬운 제어와 배포를 위해 그래픽 사용자 인터페이스(GUI)를 사용합니다.

![KVM GUI 스크린샷](https://i.imgur.com/your-screenshot-url.png) <!-- 플레이스홀더 -->

## 주요 기능

*   **GUI 제어판:** 모든 KVM 기능을 관리할 수 있는 사용하기 쉬운 인터페이스.
*   **시나리오 3 중심:** 라즈베리 파이를 중앙 입력 소스로 사용하여 다른 컴퓨터를 제어.
*   **두 가지 제어 방식:** GUI 버튼 또는 키보드 핫키(`왼쪽 Shift + 왼쪽 Ctrl + F12`)를 통해 KVM 대상 전환.
*   **양방향 클립보드 동기화:** Mac에서 복사하여 리눅스에 붙여넣기(또는 그 반대)가 가능하며, 기능을 켜고 끌 수 있음.
*   **자동화된 파이 배포:** Mac GUI의 "배포" 버튼이 라즈베리 파이의 전체 설정 과정을 자동화.

## 동작 방식

이 시스템은 세 가지 주요 구성 요소로 이루어집니다:

1.  **GUI 앱 (Mac & 리눅스):** 제어 센터 역할을 하는 `kvm_gui_app/app.py`입니다. Mac과 리눅스 PC 양쪽에서 실행합니다. 상태 정보, 제어 버튼을 제공하며, 로컬 머신의 클립보드 동기화를 처리합니다. Mac 버전에는 배포 모듈이 포함됩니다.
2.  **파이 서버 (라즈베리 파이):** 파이에서 실행되는 Flask 서버(`pi_kvm_bridge/hid_server.py`)입니다. GUI로부터 명령을 수신하고, KVM 대상 상태를 관리하며, 클립보드 콘텐츠의 중앙 허브 역할을 합니다.
3.  **파이 입력 포워더 (라즈베리 파이):** 파이에 연결된 키보드와 마우스의 입력을 캡처하여 파이 서버로 보내는 스크립트(`pi_kvm_bridge/pi_input_forwarder.py`)입니다. 대상 전환을 위한 핫키도 감지합니다.

---

## 설치 및 사용법

### 사전 준비물

*   **Python 3:** Mac, 리눅스 PC, 라즈베리 파이에 모두 설치.
*   **Git:** 이 저장소를 복제하기 위해 필요.
*   **Mac에서:** `cliclick` 설치를 위한 [Homebrew](https://brew.sh/).
*   **리눅스에서:** 클립보드 접근을 위한 `xclip` (`sudo apt install xclip`).
*   **라즈베리 파이에서:** 라즈베리 파이 OS Lite (Bookworm 권장)의 새로운 설치.

### 1단계: 프로젝트 가져오기

Mac에서 이 저장소를 복제합니다.

```bash
git clone <repository_url>
cd <repository_name>
```

### 2단계: Mac에서 앱 실행

1.  **의존성 설치:**
    ```bash
    pip3 install -r kvm_gui_app/requirements.txt
    brew install cliclick
    ```

2.  **애플리케이션 실행:**
    ```bash
    python3 kvm_gui_app/app.py
    ```
    GUI 창이 나타나야 합니다.

### 3단계: 라즈베리 파이에 배포

1.  Mac의 GUI 애플리케이션에서 **"Deploy to Pi"** 섹션을 찾습니다.
2.  라즈베리 파이의 IP 주소, 사용자, 비밀번호를 입력합니다.
3.  **Deploy** 버튼을 클릭합니다.
4.  로그 창에 파일이 복사되고 원격 설정 스크립트가 실행되는 진행 상황이 표시됩니다.
5.  로그에 "DEPLOYMENT FINISHED"가 표시되면, 안내에 따라 **라즈베리 파이를 재부팅**합니다. Mac 터미널에서 다음 명령으로 재부팅할 수 있습니다: `ssh pi@<pi_ip> 'sudo reboot'`.

### 4단계: 리눅스 PC에서 앱 실행

1.  **프로젝트 폴더 수동 복사:** Mac에서 리눅스 PC로 전체 프로젝트 폴더를 수동으로 복사합니다 (예: `scp`, USB 드라이브, 공유 폴더 사용).
    ```bash
    # 예시: 리눅스 PC에서 Mac으로부터 복사
    scp -r your_mac_user@your_mac_ip:/path/to/project_folder ~/
    ```

2.  **의존성 설치:**
    ```bash
    cd /path/to/project_folder
    sudo apt update && sudo apt install -y python3-dev xclip
    pip3 install -r kvm_gui_app/requirements.txt
    ```

3.  **애플리케이션 실행:**
    ```bash
    python3 kvm_gui_app/app.py
    ```

### 5단계: KVM 사용하기

1.  Mac과 리눅스 PC 양쪽에서 GUI 앱이 실행 중인지 확인합니다.
2.  파이가 재부팅되면 서버 구성 요소가 자동으로 시작됩니다. GUI의 상태 표시등이 녹색으로 바뀌어야 합니다.
3.  라즈베리 파이에 연결된 키보드와 마우스를 사용합니다. 입력은 GUI에 표시된 대상 머신으로 전달됩니다.
4.  **대상 전환:** 두 컴퓨터의 GUI에서 "Switch Target" 버튼을 클릭하거나, 파이의 키보드에서 `왼쪽 Shift + 왼쪽 Ctrl + F12`를 누릅니다.
5.  **클립보드 사용:** Mac과 리눅스 양쪽의 GUI에서 "Start Sync"를 클릭합니다. 이제 한 머신에서 텍스트를 복사하여 다른 머신에 붙여넣을 수 있습니다.

## 문제 해결

*   **배포 실패:**
    *   `paramiko`가 설치되었는지 확인합니다 (`pip show paramiko`).
    *   파이의 IP 주소, 사용자 이름, 비밀번호를 확인합니다.
    *   라즈베리 파이에서 SSH가 활성화되었는지 확인합니다.
*   **GUI가 연결되지 않음 (빨간불):**
    *   파이가 재부팅되었고 네트워크에 연결되었는지 확인합니다.
    *   파이의 IP 주소를 확인하고, `pi-hid-server` 서비스가 실행 중인지 확인합니다 (`systemctl status pi-hid-server`).
*   **리눅스에서 클립보드 동기화 실패:**
    *   `xclip`이 설치되었는지 확인합니다.
    *   앱이 그래픽 세션에서 실행되어야 합니다(디스플레이 서버의 클립보드에 접근 필요).
*   **Mac에서 입력 주입 실패:**
    *   `시스템 설정`에서 터미널/IDE에 **손쉬운 사용 권한**을 부여했는지 확인합니다.
