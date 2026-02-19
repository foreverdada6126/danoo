// --- 🛰️ DASHBOARD ORCHESTRATOR v5.2 ---

// Elements
const logList = document.getElementById('log-list');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const reconHistory = document.getElementById('recon-history');

// 1. CHART SYSTEM
let pnlChart;
function initChart() {
    const ctx = document.getElementById('pnlChart').getContext('2d');
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Equity',
                borderColor: '#00f2ff',
                backgroundColor: 'rgba(0, 242, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                data: [12100, 12250, 12200, 12350, 12400, 12420, 12450],
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { display: false } }
            }
        }
    });
}

// 2. OVERLAY SYSTEM
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-target');
        document.getElementById(targetId).classList.remove('hidden');
    });
});

document.querySelectorAll('.close-overlay').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.target.closest('.overlay').classList.add('hidden');
    });
});

// Close overlay on ESC
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.overlay').forEach(ov => ov.classList.add('hidden'));
    }
});

// 3. CORE UPDATES (RECON, TRADES, APPROVALS)
async function updateRecon() {
    try {
        const res = await fetch('/api/system/recon');
        const data = await res.json();
        if (!data.recon || data.recon.length === 0) return;

        const historyData = [...data.recon].reverse();
        reconHistory.innerHTML = historyData.map(item => `
            <div class="recon-item">
                <span class="time">${item.time}</span>
                <span class="title">${item.title}</span>
                <p>${item.content}</p>
            </div>
        `).join('');
    } catch (e) { console.error("Recon Sync Failed"); }
}

async function updateTrades() {
    try {
        const res = await fetch('/api/system/trades');
        const data = await res.json();
        const container = document.getElementById('trade-list');
        if (!data.trades || data.trades.length === 0) return;

        container.innerHTML = data.trades.map(t => `
            <div class="recon-item">
                <span class="time">${t.time}</span>
                <span class="title">${t.symbol} | ${t.type}</span>
                <p>Status: ${t.status} | PnL: <span class="trend up">${t.pnl}</span></p>
            </div>
        `).join('');
    } catch (e) { console.error("Trade Sync Failed"); }
}

async function updateApprovals() {
    try {
        const res = await fetch('/api/system/approvals');
        const data = await res.json();
        const container = document.getElementById('approval-list');
        if (!data.approvals || data.approvals.length === 0) return;

        container.innerHTML = data.approvals.map(a => `
            <div class="recon-item" style="border-left-color: var(--magenta);">
                <span class="time">${a.time}</span>
                <span class="title">${a.signal}</span>
                <p>AI Sentiment: ${a.sentiment} | <button class="mini-btn-outline" style="margin-top:5px; font-size: 0.5rem;">APPROVE EXECUTION</button></p>
            </div>
        `).join('');
    } catch (e) { console.error("Approval Sync Failed"); }
}

async function updateLogs() {
    try {
        const res = await fetch('/api/logs');
        const logs = await res.json();
        logList.innerHTML = logs.map(l => `
            <div class="log-entry">
                <span class="time">[${l.time}]</span>
                <span class="msg">${l.msg}</span>
            </div>
        `).join('');
        logList.scrollTop = logList.scrollHeight;
    } catch (e) { }
}

async function updateState() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        document.getElementById('equity-value').textContent = `$${data.equity.toLocaleString()}`;
        document.getElementById('regime-value').textContent = data.regime;
        document.getElementById('sentiment-value').textContent = data.sentiment_score;
        document.getElementById('ai-insight-snip').textContent = data.ai_insight;

        const bar = document.getElementById('regime-bar');
        if (bar) {
            const width = data.regime === 'BULL_TREND' ? '95%' : (data.regime === 'RANGING' ? '55%' : '15%');
            bar.style.width = width;
        }
    } catch (e) { }
}

async function updateHealth() {
    try {
        const res = await fetch('/api/system/health');
        const data = await res.json();
        document.getElementById('cpu-bar').style.width = `${data.cpu_usage}%`;
        document.getElementById('cpu-val').textContent = `${Math.round(data.cpu_usage)}%`;
        document.getElementById('ram-bar').style.width = `${data.ram_usage}%`;
        document.getElementById('ram-val').textContent = `${Math.round(data.ram_usage)}%`;
        document.getElementById('disk-bar').style.width = `${data.disk_usage}%`;
        document.getElementById('disk-val').textContent = `${Math.round(data.disk_usage)}%`;
    } catch (e) { }
}

// 4. ACTION TRIGGERS
async function sendInstruction() {
    const text = chatInput.value.trim();
    if (!text) return;
    appendMessage(text, 'user');
    chatInput.value = '';
    const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    setTimeout(() => appendMessage(data.reply, 'bot'), 500);
}

function appendMessage(text, side) {
    const div = document.createElement('div');
    div.className = `msg ${side}`;
    div.textContent = text;
    const msgContainer = document.getElementById('chat-messages');
    msgContainer.appendChild(div);
    msgContainer.scrollTop = msgContainer.scrollHeight;
}

sendBtn.addEventListener('click', sendInstruction);
chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendInstruction(); });

document.getElementById('recon-btn').addEventListener('click', async () => {
    const btn = document.getElementById('recon-btn');
    btn.textContent = "SCOUTING...";
    btn.classList.add('pulse');
    await fetch('/api/engine/recon', { method: 'POST' });
    setTimeout(() => {
        btn.textContent = "INITIATE SCAN";
        btn.classList.remove('pulse');
    }, 3000);
});

document.getElementById('report-btn').addEventListener('click', async () => {
    const term = document.getElementById('report-terminal');
    const content = document.getElementById('report-content');
    term.classList.remove('hidden');
    content.textContent = "Scanning VPS Infrastructure...";
    const res = await fetch('/api/system/report');
    const data = await res.json();
    content.textContent = data.report;
});

document.getElementById('cleanup-btn').addEventListener('click', async () => {
    if (!confirm("Purge logs?")) return;
    await fetch('/api/system/cleanup', { method: 'POST' });
    updateLogs();
});

// 5. INIT & LOOPS
initChart();
updateState();
updateHealth();
updateLogs();
updateRecon();
updateTrades();
updateApprovals();

setInterval(updateState, 2000);
setInterval(updateHealth, 3000);
setInterval(updateLogs, 2000);
setInterval(updateRecon, 3000);
setInterval(updateTrades, 5000);
setInterval(updateApprovals, 5000);

setInterval(() => {
    document.getElementById('uptime').textContent = new Date().toLocaleTimeString();
}, 1000);
