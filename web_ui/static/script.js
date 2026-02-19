// --- 🛰️ DANOO COMMAND HUB ORCHESTRATOR v5.2 ---

const get = (id) => document.getElementById(id);

// 1. CHART SYSTEM (Fixed Data Source)
let pnlChart;
function initChart() {
    const canvas = get('pnlChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Equity Growth',
                borderColor: '#00f2ff',
                backgroundColor: 'rgba(0, 242, 255, 0.05)',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                data: [],
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    border: { display: false },
                    ticks: { color: '#787b86', font: { size: 9 } }
                }
            }
        }
    });
}

async function updateChart() {
    try {
        const res = await fetch('/api/chart');
        const data = await res.json();
        pnlChart.data.labels = data.labels;
        pnlChart.data.datasets[0].data = data.values;
        pnlChart.update();
    } catch (e) { console.warn("Chart Link Down"); }
}

// 2. OVERLAY CONTROLLER
function toggleOverlay(id) {
    const el = get(id);
    if (!el) return;
    const isHidden = el.classList.contains('hidden');
    // Hide all first for cleanliness
    document.querySelectorAll('.overlay').forEach(ov => ov.classList.add('hidden'));
    if (isHidden) el.classList.remove('hidden');
}

// 3. CORE SYNC (GMGN Style)
async function syncDashboard() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();

        get('equity-value').textContent = `$${data.equity.toLocaleString()}`;
        get('regime-value').textContent = data.regime;
        get('sentiment-value').textContent = data.sentiment_score.toFixed(2);

        const regimeEl = get('regime-value');
        if (data.regime.includes('BULL')) regimeEl.className = 'val up';
        else if (data.regime.includes('BEAR')) regimeEl.className = 'val down';
        else regimeEl.className = 'val neutral';

        get('mode-tag').textContent = `${data.mode} MODE`;
        get('meta-symbol').textContent = data.symbol;
        get('orders-count').textContent = data.active_orders;
    } catch (e) { }
}

async function updateRecon() {
    try {
        const res = await fetch('/api/system/recon');
        const data = await res.json();
        const container = get('recon-history');
        if (!data.recon || data.recon.length === 0) return;

        container.innerHTML = [...data.recon].reverse().map(item => `
            <div class="card-item">
                <div class="card-meta"><span>RECON</span><span>${item.time}</span></div>
                <div class="card-header">${item.title}</div>
                <div class="card-body">${item.content}</div>
            </div>
        `).join('');
    } catch (e) { }
}

async function updateTrades() {
    try {
        const res = await fetch('/api/system/trades');
        const data = await res.json();
        const container = get('trade-list');
        if (!data.trades || data.trades.length === 0) {
            container.innerHTML = '<div class="card-item"><div class="card-body" style="color: var(--text-dim); text-align: center;">No exposure found.</div></div>';
            return;
        }

        container.innerHTML = data.trades.map(t => `
            <div class="card-item">
                <div class="card-meta"><span>${t.type}</span><span>${t.time}</span></div>
                <div class="card-header">${t.symbol} <span class="${t.pnl.includes('+') ? 'up' : 'down'}">${t.pnl}</span></div>
                <div class="card-body">Status: <span class="neutral">${t.status}</span></div>
            </div>
        `).join('');
    } catch (e) { }
}

async function updateApprovals() {
    try {
        const res = await fetch('/api/system/approvals');
        const data = await res.json();
        const container = get('approval-list');
        if (!data.approvals || data.approvals.length === 0) {
            container.innerHTML = '<div class="card-item"><div class="card-body" style="color: var(--text-dim); text-align: center;">Queue empty.</div></div>';
            return;
        }

        container.innerHTML = data.approvals.map((a, index) => `
            <div class="card-item" style="border-left: 2px solid var(--magenta);">
                <div class="card-meta"><span>SIGNAL</span><span>${a.time}</span></div>
                <div class="card-header">${a.signal}</div>
                <div class="card-body">AI Sentiment: ${a.sentiment} <button class="btn-sm" style="font-size: 0.5rem; float:right;" onclick="approveTrade(${index})">APPROVE</button></div>
            </div>
        `).join('');
    } catch (e) { }
}

async function approveTrade(id) {
    try {
        const res = await fetch(`/api/system/approve/${id}`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            updateApprovals();
            updateTrades();
            syncDashboard();
            updateChart();
        }
    } catch (e) { console.error("Approval failed"); }
}

async function updateHealth() {
    try {
        const res = await fetch('/api/system/health');
        const data = await res.json();
        get('cpu-val').textContent = `${Math.round(data.cpu_usage)}%`;
        get('ram-val').textContent = `${Math.round(data.ram_usage)}%`;
        get('disk-val').textContent = `${Math.round(data.disk_usage)}%`;
    } catch (e) { }
}

async function updateLogs() {
    try {
        const res = await fetch('/api/logs');
        const logs = await res.json();
        const container = get('log-list');
        container.innerHTML = logs.map(l => `
            <div style="margin-bottom: 5px; opacity: 0.7;">
                <span class="neutral">[${l.time}]</span> ${l.msg}
            </div>
        `).join('');
        container.scrollTop = container.scrollHeight;
    } catch (e) { }
}

// 4. CHAT INTERFACE
async function sendCommand() {
    const input = get('chat-input');
    if (!input || !input.value.trim()) return;
    const text = input.value.trim();
    appendMsg(text, 'user');
    input.value = '';
    const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    setTimeout(() => appendMsg(data.reply, 'bot'), 400);
}

function appendMsg(text, side) {
    const list = get('chat-messages');
    const div = document.createElement('div');
    div.className = `msg ${side}`;
    div.textContent = text;
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
}

// 5. BOOTSTRAP
document.addEventListener('DOMContentLoaded', () => {
    initChart();

    // Bind Globals
    window.toggleOverlay = toggleOverlay;
    get('send-btn').onclick = sendCommand;
    get('chat-input').onkeypress = (e) => { if (e.key === 'Enter') sendCommand(); };

    get('recon-btn').onclick = async () => {
        get('recon-btn').classList.add('pulse');
        await fetch('/api/engine/recon', { method: 'POST' });
        setTimeout(() => get('recon-btn').classList.remove('pulse'), 2000);
    };

    get('report-btn').onclick = async () => {
        get('report-terminal').classList.remove('hidden');
        get('report-content').textContent = "Scanning infrastructure...";
        const res = await fetch('/api/system/report');
        const data = await res.json();
        get('report-content').textContent = data.report;
    };

    get('cleanup-btn').onclick = async () => {
        if (!confirm("Purge logs?")) return;
        await fetch('/api/system/cleanup', { method: 'POST' });
        updateLogs();
    };

    // Loops
    setInterval(syncDashboard, 1500);
    setInterval(updateChart, 3000); // Dynamic chart update
    setInterval(updateHealth, 3000);
    setInterval(updateLogs, 2000);
    setInterval(updateRecon, 3000);
    setInterval(updateTrades, 3000);
    setInterval(updateApprovals, 3000);
    setInterval(() => {
        const up = get('uptime');
        if (up) {
            const now = new Date();
            up.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        }
    }, 1000);
});
