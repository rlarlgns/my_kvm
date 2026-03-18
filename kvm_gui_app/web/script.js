// kvm_gui_app/web/script.js

window.addEventListener('pywebviewready', () => {
    getStatus();
    setInterval(getStatus, 3000);
});

const serverStatusEl = document.getElementById('server-status');
const currentTargetEl = document.getElementById('current-target');
const macStatusEl = document.getElementById('mac-status');
const linuxStatusEl = document.getElementById('linux-status');
const switchTargetBtn = document.getElementById('switch-target-btn');
const clipboardStatusEl = document.getElementById('clipboard-status');
const toggleClipboardBtn = document.getElementById('toggle-clipboard-btn');
const deployBtn = document.getElementById('deploy-btn');
const runCheckerBtn = document.getElementById('run-checker-btn');
const deployLogEl = document.getElementById('deploy-log');

const piIpEl = document.getElementById('pi-ip');
const piUserEl = document.getElementById('pi-user');
const piPassEl = document.getElementById('pi-pass');

async function callApi(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, options);
        if (!response.ok) throw new Error('API Error');
        return await response.json();
    } catch (error) {
        if (endpoint === '/api/status') updateStatus({ server_status: 'offline' });
        throw error;
    }
}

async function getStatus() {
    try {
        const data = await callApi('/api/status');
        updateStatus(data);
    } catch (error) {}
}

function updateStatus(data) {
    if (data.server_status === 'online') {
        serverStatusEl.classList.add('online');
        switchTargetBtn.disabled = false;
    } else {
        serverStatusEl.classList.remove('online');
        currentTargetEl.textContent = '--';
        macStatusEl.textContent = 'Disconnected';
        macStatusEl.classList.remove('active');
        linuxStatusEl.textContent = 'Disconnected';
        linuxStatusEl.classList.remove('active');
        switchTargetBtn.disabled = true;
    }

    if (data.kvm_target) currentTargetEl.textContent = data.kvm_target.toUpperCase();

    if (data.mac_connected) {
        macStatusEl.textContent = 'Connected';
        macStatusEl.classList.add('active');
    } else {
        macStatusEl.textContent = 'Disconnected';
        macStatusEl.classList.remove('active');
    }

    if (data.linux_connected) {
        linuxStatusEl.textContent = 'Connected';
        linuxStatusEl.classList.add('active');
    } else {
        linuxStatusEl.textContent = 'Disconnected';
        linuxStatusEl.classList.remove('active');
    }
    
    if (data.clipboard_status === 'active') {
        clipboardStatusEl.textContent = 'Active';
        clipboardStatusEl.classList.add('active');
        toggleClipboardBtn.textContent = 'Stop Sync';
    } else {
        clipboardStatusEl.textContent = 'Inactive';
        clipboardStatusEl.classList.remove('active');
        toggleClipboardBtn.textContent = 'Start Sync';
    }
}

function logToDeploy(message) {
    deployLogEl.textContent += message;
    deployLogEl.scrollTop = deployLogEl.scrollHeight;
}

switchTargetBtn.addEventListener('click', async () => {
    try {
        const current = currentTargetEl.textContent.toLowerCase();
        const next = (current === 'mac' ? 'linux' : 'mac');
        await callApi('/api/switch_target', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target: next })
        });
        getStatus();
    } catch (error) {}
});

toggleClipboardBtn.addEventListener('click', async () => {
    try {
        await callApi('/api/toggle_clipboard', { method: 'POST' });
        getStatus();
    } catch (error) {}
});

deployBtn.addEventListener('click', async () => {
    deployLogEl.textContent = 'Starting deployment to Pi...\n';
    deployBtn.disabled = true;
    runCheckerBtn.disabled = true;
    const payload = { ip: piIpEl.value, user: piUserEl.value, password: piPassEl.value };
    try {
        const response = await fetch('/api/deploy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            logToDeploy(decoder.decode(value, { stream: true }));
        }
    } catch (error) {
        logToDeploy('\nError: ' + error.message);
    } finally {
        deployBtn.disabled = false;
        runCheckerBtn.disabled = false;
    }
});

runCheckerBtn.addEventListener('click', async () => {
    deployLogEl.textContent = 'Running Pi device checker...\n';
    deployBtn.disabled = true;
    runCheckerBtn.disabled = true;
    const payload = { ip: piIpEl.value, user: piUserEl.value, password: piPassEl.value };
    try {
        const response = await fetch('/api/run_checker', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            logToDeploy(decoder.decode(value, { stream: true }));
        }
    } catch (error) {
        logToDeploy('\nError: ' + error.message);
    } finally {
        deployBtn.disabled = false;
        runCheckerBtn.disabled = false;
    }
});
