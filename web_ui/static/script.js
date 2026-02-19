const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const logList = document.getElementById('log-list');

// Initialize Chart.js
let pnlChart;
function initChart() {
    const ctx = document.getElementById('pnlChart').getContext('2d');
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Equity Growth',
                borderColor: '#00f2ff',
                backgroundColor: 'rgba(0, 242, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                data: [],
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#8b949e', font: { size: 10 } }
                }
            }
        }
    });
}

// Fetch and Render Chart Data
async function loadChartData() {
    const res = await fetch('/api/chart');
    const data = await res.json();
    pnlChart.data.labels = data.labels;
    pnlChart.data.datasets[0].data = data.values;
    pnlChart.update();
}

// Fetch and Render Logs
async function updateLogs() {
    const res = await fetch('/api/logs');
    const logs = await res.json();
    logList.innerHTML = logs.map(l => `
        <div class="log-entry">
            <span class="time">[${l.time}]</span>
            <span class="msg">${l.msg}</span>
        </div>
    `).join('');
    logList.scrollTop = logList.scrollHeight;
}

async function sendInstruction() {
    const text = chatInput.value.trim();
    if (!text) return;
    appendMessage(text, 'user');
    chatInput.value = '';
    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await response.json();
    setTimeout(() => appendMessage(data.reply, 'bot'), 500);
}

function appendMessage(text, side) {
    const div = document.createElement('div');
    div.className = `msg ${side}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

sendBtn.addEventListener('click', sendInstruction);
chatInput.addEventListener('keypress', (e) => { e.key === 'Enter' && sendInstruction(); });

// Periodic Status Updates
async function updateState() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        document.getElementById('equity-value').textContent = `$${data.equity.toLocaleString()}`;
        document.getElementById('regime-value').textContent = data.regime;

        // New elements
        if (document.getElementById('sentiment-value'))
            document.getElementById('sentiment-value').textContent = data.sentiment_score;
        if (document.getElementById('ai-insight-snip'))
            document.getElementById('ai-insight-snip').textContent = data.ai_insight;

        // Heartbeat / Background Activity
        const hb = document.getElementById('heartbeat-tag');
        hb.textContent = data.heartbeat;
        hb.className = 'tag ' + data.heartbeat.toLowerCase();

        // Dynamic Regime Bar
        const bar = document.getElementById('regime-bar');
        if (bar) {
            const width = data.regime === 'BULL_TREND' ? '95%' : (data.regime === 'RANGING' ? '55%' : '15%');
            bar.style.width = width;
        }

    } catch (e) { console.error("Update failed"); }
}

// File Vault Logic
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const fileTarget = document.getElementById('file-target');
const fileList = document.getElementById('file-list');

async function updateFileList() {
    const res = await fetch('/api/files');
    const data = await res.json();

    let html = '';

    html += '<div class="file-category">REFERENCE</div>';
    data.reference.forEach(f => {
        html += `<div class="file-item"><span>${f}</span><button onclick="deleteFile('${f}', 'reference')">DEL</button></div>`;
    });

    html += '<div class="file-category">DATA</div>';
    data.processed_data.forEach(f => {
        html += `<div class="file-item"><span>${f}</span><button onclick="deleteFile('${f}', 'data')">DEL</button></div>`;
    });

    fileList.innerHTML = html;
}

uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async () => {
    if (fileInput.files.length === 0) return;
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    await fetch(`/api/files/upload?target=${fileTarget.value}`, {
        method: 'POST',
        body: formData
    });
    fileInput.value = '';
    updateFileList();
});

async function deleteFile(filename, target) {
    await fetch(`/api/files/${filename}?target=${target}`, { method: 'DELETE' });
    updateFileList();
}

// DevOps Logic
const gitSyncBtn = document.getElementById('git-sync-btn');

async function syncToGithub() {
    gitSyncBtn.textContent = "SYNCING...";
    gitSyncBtn.classList.add('pulse');

    try {
        const res = await fetch('/api/system/git_sync', { method: 'POST' });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("Fatal Sync Error: Check VPS logs.");
    } finally {
        gitSyncBtn.textContent = "PUSH TO GITHUB";
        gitSyncBtn.classList.remove('pulse');
        updateSystemInfo();
    }
}

async function updateSystemInfo() {
    const res = await fetch('/api/system/info');
    const data = await res.json();
    document.getElementById('meta-version').textContent = data.version;
    document.getElementById('meta-hash').textContent = `#${data.git_hash}`;
}

const cleanupBtn = document.getElementById('cleanup-btn');

async function updateHealth() {
    try {
        const res = await fetch('/api/system/health');
        const data = await res.json();

        document.getElementById('cpu-bar').style.width = `${data.cpu_usage}%`;
        document.getElementById('cpu-val').textContent = `${data.cpu_usage}%`;

        document.getElementById('ram-bar').style.width = `${data.ram_usage}%`;
        document.getElementById('ram-val').textContent = `${data.ram_usage}%`;

        document.getElementById('disk-bar').style.width = `${data.disk_usage}%`;
        document.getElementById('disk-val').textContent = `${data.disk_usage}%`;
    } catch (e) { console.error("Health update failed"); }
}

async function purgeLogs() {
    if (!confirm("Are you sure you want to clear system logs?")) return;
    cleanupBtn.textContent = "PURGING...";
    try {
        const res = await fetch('/api/system/cleanup', { method: 'POST' });
        const data = await res.json();
        updateLogs();
    } catch (e) { alert("Cleanup failed."); }
    finally { cleanupBtn.textContent = "PURGE LOGS"; }
}

gitSyncBtn.addEventListener('click', syncToGithub);
cleanupBtn.addEventListener('click', purgeLogs);
document.getElementById('report-btn').addEventListener('click', async () => {
    const term = document.getElementById('report-terminal');
    const content = document.getElementById('report-content');
    term.classList.remove('hidden');
    content.textContent = "Scanning VPS Infrastructure...";

    try {
        const res = await fetch('/api/system/report');
        const data = await res.json();
        content.textContent = data.report;
    } catch (e) { content.textContent = "Report Scan Failed: Connectivity Error."; }
});
document.getElementById('regime-btn').addEventListener('click', async () => {
    const btn = document.getElementById('regime-btn');
    btn.classList.add('pulse');
    await fetch('/api/engine/scan', { method: 'POST' });
    setTimeout(() => {
        btn.classList.remove('pulse');
        updateLogs();
    }, 1000);
});

// Initialization - INSTANT LOAD
initChart();
loadChartData();
updateLogs();
updateFileList();
updateSystemInfo();
updateHealth();
updateState();

// High-Frequency Sync (1.5s - 2s)
setInterval(updateState, 1500);
setInterval(updateHealth, 1500);
setInterval(updateLogs, 2000);

// Background Sync
setInterval(loadChartData, 60000);
setInterval(updateFileList, 15000);
setInterval(updateSystemInfo, 30000);

setInterval(() => {
    document.getElementById('uptime').textContent = new Date().toLocaleTimeString();
}, 1000);
