// --- 🛰️ DANOO COMMAND HUB ORCHESTRATOR v5.2 ---

const get = (id) => document.getElementById(id);

let expandedGroups = new Set();

function toggleReconGroup(dateId) {
    console.log("Toggling Group:", dateId);
    if (expandedGroups.has(dateId)) {
        expandedGroups.delete(dateId);
    } else {
        expandedGroups.add(dateId);
    }
    const el = document.getElementById(`recon-group-${dateId}`);
    if (el) {
        el.classList.toggle('collapsed', !expandedGroups.has(dateId));
    }
}

// Helper: Format Server Timestamp to Local Browser Time
function formatTime(ts, seconds = false) {
    if (!ts) return '--:--';
    // Handle Unix seconds or JS ISO strings
    const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
    if (isNaN(d.getTime())) return ts; // Return as-is if already a string
    const opts = { hour: '2-digit', minute: '2-digit', hour12: false };
    if (seconds) opts.second = '2-digit';
    return d.toLocaleTimeString([], opts);
}

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
async function toggleAI() {
    try {
        const res = await fetch('/api/system/toggle_ai', { method: 'POST' });
        const data = await res.json();
        syncDashboard();
    } catch (e) {
        console.error("Failed to toggle AI", e);
    }
}

async function syncDashboard() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();

        get('equity-value').textContent = `$${data.equity.toLocaleString()}`;
        get('regime-value').textContent = data.regime;
        get('sentiment-value').textContent = data.sentiment_score.toFixed(2);
        get('price-value').textContent = `$${data.price.toLocaleString()}`;
        get('funding-value').textContent = `${data.funding_rate}%`;

        const regimeEl = get('regime-value');
        if (data.regime.includes('BULL')) regimeEl.className = 'val up';
        else if (data.regime.includes('BEAR')) regimeEl.className = 'val down';
        else regimeEl.className = 'val neutral';

        get('mode-tag').textContent = `${data.mode} MODE`;
        get('meta-symbol').textContent = data.symbol;
        get('orders-count').textContent = data.active_orders;

        const exchangeStatusEl = get('exchange-status');
        const exchangeDotEl = get('exchange-dot');
        const exchangeNameEl = get('exchange-name');

        if (exchangeStatusEl) {
            exchangeNameEl.textContent = data.exchange_id || "EXCHANGE";
            if (data.exchange_connected) {
                exchangeStatusEl.style.background = "rgba(0, 255, 100, 0.1)";
                exchangeStatusEl.style.color = "#00ff64";
                exchangeStatusEl.style.borderColor = "#00ff6422";
                exchangeDotEl.style.background = "#00ff64";
                exchangeDotEl.style.boxShadow = "0 0 5px #00ff64";
            } else {
                exchangeStatusEl.style.background = "rgba(255, 100, 100, 0.1)";
                exchangeStatusEl.style.color = "#ff6464";
                exchangeStatusEl.style.borderColor = "#ff646422";
                exchangeDotEl.style.background = "#ff6464";
                exchangeDotEl.style.boxShadow = "0 0 5px #ff6464";
            }
        }

        const aiBtn = get('ai-toggle-btn');
        if (aiBtn) {
            if (data.ai_active) {
                aiBtn.textContent = "AI: ON";
                aiBtn.style.background = "rgba(0, 255, 100, 0.1)";
                aiBtn.style.color = "#00ff64";
                aiBtn.style.borderColor = "#00ff6422";
            } else {
                aiBtn.textContent = "AI: OFF";
                aiBtn.style.background = "rgba(255, 100, 100, 0.1)";
                aiBtn.style.color = "#ff6464";
                aiBtn.style.borderColor = "#ff646422";
            }
        }
    } catch (e) { }
}

async function updateRecon() {
    try {
        const res = await fetch('/api/system/recon');
        const data = await res.json();
        const container = get('recon-history');

        if (!data.recon_groups || data.recon_groups.length === 0) {
            // If empty, we can show a subtle message or keep previous state
            return;
        }

        // Auto-expand first group if nothing is expanded
        if (expandedGroups.size === 0 && data.recon_groups.length > 0) {
            expandedGroups.add(data.recon_groups[0].date_id);
        }

        const html = data.recon_groups.map(group => {
            const isColl = !expandedGroups.has(group.date_id);
            const pnlCls = group.daily_pnl > 0 ? 'up' : (group.daily_pnl < 0 ? 'down' : '');

            return `
                <div id="recon-group-${group.date_id}" class="recon-group ${isColl ? 'collapsed' : ''}">
                    <div class="recon-date-header ${pnlCls}" onclick="toggleReconGroup('${group.date_id}')">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span>${group.date}</span>
                            <span class="recon-meta">Close: $${(group.closing_price || 0).toLocaleString()}</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:12px;">
                            <span class="recon-meta ${pnlCls}" style="font-weight:700;">PnL: $${(group.daily_pnl || 0).toFixed(2)}</span>
                            <span class="chevron">▼</span>
                        </div>
                    </div>
                    <div class="recon-items-content">
                        ${group.items.map(item => `
                            <div class="card-item sub-item">
                                <div class="card-meta"><span>RECON</span><span>${formatTime(item.time)}</span></div>
                                <div class="card-header">${item.title}</div>
                                <div class="card-body">${item.content}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = html;
    } catch (err) {
        console.error("Recon Update Failed:", err);
    }
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
                <div class="card-meta"><span>${t.type}</span><span>${formatTime(t.time)}</span></div>
                <div class="card-header">${t.symbol} <span class="${t.pnl.includes('+') ? 'up' : 'down'}">${t.pnl}</span></div>
                <div class="card-body">
                    Status: <span class="neutral">${t.status}</span>
                    <div style="font-size: 0.6rem; color: var(--text-dim); margin-top: 4px; font-style: italic;">Reason: ${t.reason || 'Not specified'}</div>
                    <button onclick="closeTrade('${t.order_id}')" class="btn btn-approve" style="margin-top: 10px; width: 100%; font-size: 0.6rem; background: rgba(255, 100, 100, 0.1); border-color: #ff6464; color: #ff6464;">CLOSE POSITION</button>
                </div>
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
                <div class="card-meta"><span>SIGNAL</span><span>${formatTime(a.time)}</span></div>
                <div class="card-header">${a.signal}</div>
                <div class="card-body">
                    AI Sentiment: ${a.sentiment}
                    <div style="font-size: 0.6rem; color: var(--text-dim); margin-bottom: 6px;">${a.reason || 'Pending scan justification...'}</div>
                    <button class="btn-sm" style="font-size: 0.5rem; float:right;" onclick="approveTrade(${index})">APPROVE</button>
                </div>
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
        } else {
            alert(`Execution Error: ${data.message}`);
        }
    } catch (e) {
        console.error("Approval failed", e);
        alert("System Error: Could not connect to the Bridge.");
    }
}

async function closeTrade(order_id) {
    try {
        const res = await fetch(`/api/system/close/${order_id}`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            updateTrades();
            syncDashboard();
            updateChart();
        } else {
            alert(`Closure Error: ${data.message}`);
        }
    } catch (e) {
        console.error("Closure failed", e);
        alert("System Error: Could not broadcast closure signal.");
    }
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
        const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 20;

        container.innerHTML = logs.map(l => `
            <div style="margin-bottom: 5px; opacity: 0.7;">
                <span class="neutral">[${formatTime(l.time, true)}]</span> ${l.msg}
            </div>
        `).join('');

        if (isScrolledToBottom) {
            container.scrollTop = container.scrollHeight;
        }
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
    window.toggleReconGroup = toggleReconGroup;
    window.toggleFabChat = () => {
        const box = get('master-command-box');
        if (box) box.classList.toggle('hidden');
    };

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

    // Draggable FAB Logic
    const fabBox = get('master-command-box');
    const dragHandle = get('fab-drag-handle');
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;

    if (dragHandle && fabBox) {
        dragHandle.addEventListener('mousedown', (e) => {
            isDragging = true;
            const rect = fabBox.getBoundingClientRect();
            dragStartX = e.clientX - rect.left;
            dragStartY = e.clientY - rect.top;
            dragHandle.style.cursor = 'grabbing';
            // Disable transition during drag for smoothness
            fabBox.style.transition = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            e.preventDefault();

            let newX = e.clientX - dragStartX;
            let newY = e.clientY - dragStartY;

            const rect = fabBox.getBoundingClientRect();
            if (newX < 0) newX = 0;
            if (newY < 0) newY = 0;
            if (newX + rect.width > window.innerWidth) newX = window.innerWidth - rect.width;
            if (newY + rect.height > window.innerHeight) newY = window.innerHeight - rect.height;

            // Break out of the static bottom/right layout
            fabBox.style.position = 'fixed';
            fabBox.style.bottom = 'auto';
            fabBox.style.right = 'auto';
            fabBox.style.left = `${newX}px`;
            fabBox.style.top = `${newY}px`;
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                dragHandle.style.cursor = 'grab';
            }
        });
    }
});
