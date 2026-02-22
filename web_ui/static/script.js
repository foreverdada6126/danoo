const get = (id) => document.getElementById(id);

let expandedGroups = new Set();
let activeLogTab = "ALL";
let isDraggingFab = false;

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
        if (!res.ok) throw new Error("Server Log Error");
        let logs = await res.json();
        const container = get('log-list');
        if (!container) return;

        // Filter by Tab
        if (activeLogTab !== "ALL") {
            logs = logs.filter(l => l.cat === activeLogTab);
        }

        if (!logs || logs.length === 0) {
            container.innerHTML = `<div class="text-[10px] text-brand-dim text-center py-10 italic">No events found for ${activeLogTab}</div>`;
            return;
        }

        const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 100;

        container.innerHTML = logs.map(l => {
            const levelMatch = l.msg.match(/^\[(INFO|ERROR|DEBUG|SUCCESS|WARNING)\]/);
            const level = levelMatch ? levelMatch[1] : 'INFO';
            const cleanMsg = l.msg.replace(/^\[.*?\]/, '').trim();
            const color = level === 'ERROR' ? '#ff4444' : (level === 'SUCCESS' ? '#00ff64' : (level === 'WARNING' ? '#ffbb00' : '#fff'));

            return `
                <div style="margin-bottom: 8px; font-size: 11px; line-height: 1.4; border-bottom: 1px solid rgba(255,255,255,0.03); padding-bottom: 4px; display: flex; gap: 8px;">
                    <span style="color: var(--cyan-brand); font-weight: bold; min-width: 60px;">${formatTime(l.time, true)}</span>
                    <span style="color: ${color}; opacity: 0.9;">${cleanMsg}</span>
                </div>
            `;
        }).join('');

        if (isScrolledToBottom) {
            container.scrollTop = container.scrollHeight;
        }
    } catch (e) {
        console.error("Logs sync failed", e);
        const container = get('log-list');
        if (container) container.innerHTML = `<div class="text-red-500/50 text-[10px] text-center py-4">Sync Error: ${e.message}</div>`;
    }
}

async function updateFiles() {
    try {
        const res = await fetch('/api/files');
        const data = await res.json();
        const container = get('file-list');
        if (!container) return;

        const target = get('file-target').value;
        const files = target === "reference" ? data.reference : data.processed_data;

        if (!files || files.length === 0) {
            container.innerHTML = '<div class="py-4 text-center opacity-30 italic">No assets discovered.</div>';
            return;
        }

        container.innerHTML = files.map(f => `
            <div class="flex items-center justify-between p-2 rounded bg-white/5 border border-white/5 group">
                <div class="flex items-center gap-2 overflow-hidden">
                    <span class="text-brand-cyan">📄</span>
                    <span class="truncate">${f}</span>
                </div>
                <button onclick="deleteFile('${f}')" class="opacity-0 group-hover:opacity-100 text-brand-red transition-opacity px-2">×</button>
            </div>
        `).join('');
    } catch (e) { }
}

async function deleteFile(filename) {
    if (!confirm(`Relinquish ${filename}?`)) return;
    const target = get('file-target').value;
    try {
        await fetch(`/api/files/${filename}?target=${target}`, { method: 'DELETE' });
        updateFiles();
    } catch (e) { }
}

function setLogTab(category) {
    activeLogTab = category;
    document.querySelectorAll('.log-tab').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-category') === category);
    });
    updateLogs();
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
    // Bind Globals
    window.toggleOverlay = toggleOverlay;
    window.toggleReconGroup = toggleReconGroup;
    window.setLogTab = setLogTab;

    window.toggleFabMenu = (e) => {
        if (isDraggingFab) return;
        const menu = get('fab-menu');
        if (menu) menu.classList.toggle('hidden');
    };

    window.openFabAction = (action) => {
        get('fab-menu').classList.add('hidden'); // Close menu after choice

        if (action === 'command') {
            get('master-command-box').classList.toggle('hidden');
        } else if (action === 'logs') {
            toggleOverlay('logs-overlay');
        } else if (action === 'files') {
            toggleOverlay('files-overlay');
        }
    };

    window.toggleFabChat = (e) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        const box = get('master-command-box');
        if (box) {
            box.classList.toggle('hidden');
        }
    };

    const sendBtn = get('send-btn');
    if (sendBtn) sendBtn.onclick = sendCommand;

    const chatInput = get('chat-input');
    if (chatInput) chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendCommand(); };

    const reconBtn = get('recon-btn');
    if (reconBtn) {
        reconBtn.onclick = async () => {
            reconBtn.classList.add('pulse');
            await fetch('/api/engine/recon', { method: 'POST' });
            setTimeout(() => reconBtn.classList.remove('pulse'), 2000);
        };
    }

    const cleanupBtn = get('cleanup-btn');
    if (cleanupBtn) {
        cleanupBtn.onclick = async () => {
            if (!confirm("Purge logs?")) return;
            await fetch('/api/system/cleanup', { method: 'POST' });
            updateLogs();
        };
    }

    // Loops
    setInterval(syncDashboard, 1500);
    setInterval(updateChart, 5000);
    setInterval(updateHealth, 5000);
    setInterval(updateLogs, 2000);
    setInterval(updateRecon, 5000);
    setInterval(updateTrades, 3000);
    setInterval(updateApprovals, 3000);
    setInterval(updateFiles, 10000);
    setInterval(() => {
        const up = get('uptime');
        if (up) {
            const now = new Date();
            up.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        }
    }, 1000);

    // Draggable FAB Logic
    const fabWidget = get('fab-widget');
    const dragHandle = get('fab-drag-handle');
    const fabButton = get('fab-button');
    let dragStartX = 0;
    let dragStartY = 0;

    function initDrag(e) {
        // Stop drag if clicking buttons inside the box (except the handle itself)
        if (e.target.tagName && e.target.tagName.toLowerCase() === 'button' && e.currentTarget.id !== 'fab-button') return;

        console.log("Drag Started from:", e.currentTarget.id);
        isDraggingFab = false;

        const rect = fabWidget.getBoundingClientRect();

        // Reset positioning to handle dragging correctly (remove bottom/right)
        fabWidget.style.right = 'auto';
        fabWidget.style.bottom = 'auto';
        fabWidget.style.left = `${rect.left}px`;
        fabWidget.style.top = `${rect.top}px`;

        dragStartX = e.clientX - rect.left;
        dragStartY = e.clientY - rect.top;

        document.addEventListener('mousemove', onDragMove);
        document.addEventListener('mouseup', onDragEnd);

        // Visual feedback for drag state
        document.body.style.cursor = 'grabbing';
    }

    function onDragMove(e) {
        if (!isDraggingFab) isDraggingFab = true;
        e.preventDefault();

        let newX = e.clientX - dragStartX;
        let newY = e.clientY - dragStartY;

        // Constraint check - keep it well within view
        const pad = 5;
        if (newX < pad) newX = pad;
        if (newY < pad) newY = pad;
        if (newX > window.innerWidth - 70) newX = window.innerWidth - 70;
        if (newY > window.innerHeight - 70) newY = window.innerHeight - 70;

        fabWidget.style.left = `${newX}px`;
        fabWidget.style.top = `${newY}px`;
    }

    function onDragEnd(e) {
        document.removeEventListener('mousemove', onDragMove);
        document.removeEventListener('mouseup', onDragEnd);
        document.body.style.cursor = 'default';

        console.log("Drag Ended. Was dragging:", isDraggingFab);
        // Block click if it was a drag
        setTimeout(() => { isDraggingFab = false; }, 250);
    }

    if (dragHandle) dragHandle.addEventListener('mousedown', initDrag);
    if (fabButton) fabButton.addEventListener('mousedown', initDrag);
});
