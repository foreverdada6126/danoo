const get = (id) => document.getElementById(id);

let expandedGroups = new Set();
let activeLogTab = "ALL";
let isDraggingFab = false;
let activeTradeTab = "ALL";
let activeStratFilter = "ALL";
let isIntelCollapsed = true;
let lastReadIntelTime = 0;

function setStratFilter(cat) {
    activeStratFilter = cat;
    const btns = document.querySelectorAll('#strat-filter-nav button[data-strat]');
    btns.forEach(b => {
        if (b.dataset.strat === cat) b.classList.add('active');
        else b.classList.remove('active');
    });
    updateTrades();
}

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
        if (pnlChart && pnlChart.data) {
            pnlChart.data.labels = data.labels;
            pnlChart.data.datasets[0].data = data.values;
            pnlChart.update();
        }
    } catch (e) {
        console.warn('Chart Link Down');
    }
}

window.refreshChartData = async () => {
    // Relying on global window.candleSeries created in HTML
    if (typeof window.candleSeries === 'undefined' || !window.candleSeries) return;
    try {
        const currentSymbol = document.getElementById('asset-selector')?.value || 'BTCUSDT';
        const currentTimeframe = document.getElementById('timeframe-selector')?.value || '15m';
        const res = await fetch(`/api/chart/ohlcv?symbol=${currentSymbol}&timeframe=${currentTimeframe}`);
        const data = await res.json();
        if (data.candles && data.candles.length > 0) {
            window.candleSeries.setData(data.candles);
        }
        if (data.trades && data.trades.length > 0) {
            window.candleSeries.setMarkers(data.trades);
        }
    } catch (e) {
        console.warn('Failed to refresh chart:', e);
    }
};

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

        if (get('equity-value')) get('equity-value').textContent = `$${data.equity.toLocaleString()}`;
        if (get('perf-capital')) get('perf-capital').textContent = `$${data.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (get('perf-pnl')) {
            const pnl = data.pnl_24h || 0;
            const sign = pnl > 0 ? '+' : '';
            const val = Math.abs(pnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const pnlEl = get('perf-pnl');
            pnlEl.textContent = `${sign}$${val}`;
            pnlEl.className = `text-lg font-bold font-mono tracking-wider ${pnl > 0 ? 'text-brand-green' : (pnl < 0 ? 'text-brand-red' : 'text-white')}`;
        }
        if (get('regime-value')) {
            const regimeEl = get('regime-value');
            regimeEl.textContent = data.regime;
            if (data.regime.includes('BULL')) regimeEl.className = 'val up';
            else if (data.regime.includes('BEAR')) regimeEl.className = 'val down';
            else regimeEl.className = 'val neutral';
        }
        if (get('sentiment-value')) get('sentiment-value').textContent = data.sentiment_score.toFixed(2);
        if (get('price-value')) get('price-value').textContent = `$${data.price.toLocaleString()}`;
        if (get('funding-value')) get('funding-value').textContent = `${data.funding_rate}%`;

        if (get('mode-selector') && data.mode) {
            const ms = get('mode-selector');
            if (ms.value !== data.mode.toLowerCase()) {
                ms.value = data.mode.toLowerCase();
            }
            if (data.mode.toLowerCase() === 'live') {
                ms.classList.remove('text-brand-dim');
                ms.classList.add('text-brand-red');
            } else {
                ms.classList.remove('text-brand-red');
                ms.classList.add('text-brand-dim');
            }
        }

        if (get('meta-symbol')) get('meta-symbol').textContent = data.symbol;
        if (get('orders-count')) get('orders-count').textContent = data.active_orders;

        const exchangeStatusEl = get('exchange-status');
        const exchangeDotEl = get('exchange-dot');
        const exchangeNameEl = get('exchange-name');

        if (exchangeStatusEl) {
            if (exchangeNameEl) exchangeNameEl.textContent = data.exchange_id || "EXCHANGE";
            if (data.exchange_connected) {
                exchangeStatusEl.style.background = "rgba(0, 255, 100, 0.1)";
                exchangeStatusEl.style.color = "#00ff64";
                exchangeStatusEl.style.borderColor = "#00ff6422";
                if (exchangeDotEl) {
                    exchangeDotEl.style.background = "#00ff64";
                    exchangeDotEl.style.boxShadow = "0 0 5px #00ff64";
                }
            } else {
                exchangeStatusEl.style.background = "rgba(255, 100, 100, 0.1)";
                exchangeStatusEl.style.color = "#ff6464";
                exchangeStatusEl.style.borderColor = "#ff646422";
                if (exchangeDotEl) {
                    exchangeDotEl.style.background = "#ff6464";
                    exchangeDotEl.style.boxShadow = "0 0 5px #ff6464";
                }
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
        const archiveContainer = get('recon-history');
        const miniContainer = get('recent-intel-content');

        if (!data.recon_groups || data.recon_groups.length === 0) return;

        // 1. Update Archives Overlay
        if (archiveContainer) {
            const filterAsset = get('recon-asset-filter') ? get('recon-asset-filter').value : 'ALL';

            // Generate filtered groups
            const filteredGroups = data.recon_groups.map(group => {
                const filteredItems = group.items.filter(item => {
                    if (filterAsset === 'ALL') return true;
                    // Check if title contains the asset (e.g. "AUTO-SCAN: BTC")
                    return item.title.includes(filterAsset);
                });
                return { ...group, items: filteredItems };
            }).filter(group => group.items.length > 0);

            if (filteredGroups.length === 0) {
                archiveContainer.innerHTML = `<div class="text-[10px] text-brand-dim text-center py-20 italic">No reports found for ${filterAsset}</div>`;
            } else {
                if (expandedGroups.size === 0) expandedGroups.add(filteredGroups[0].date_id);
                archiveContainer.innerHTML = filteredGroups.map(group => {
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
                                    <span class="recon-meta ${pnlCls}">PnL: $${(group.daily_pnl || 0).toFixed(2)}</span>
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
            }
        }

        // 2. Update Mini-Slot (Directly above Approval Queue)
        if (miniContainer) {
            const latestAction = data.recon_groups[0].items[0];
            const notif = get('intel-notif');

            // Check for new unread intel
            if (latestAction.time > lastReadIntelTime) {
                if (notif && isIntelCollapsed) {
                    notif.classList.remove('hidden');
                }
                // If not collapsed, we assume they saw it, but let's be safe:
                // only mark as read if it's currently expanded
                if (!isIntelCollapsed) {
                    lastReadIntelTime = latestAction.time;
                }
            }

            miniContainer.innerHTML = `
                <div class="card-item" style="border-color: rgba(0, 242, 255, 0.2); background: rgba(0, 242, 255, 0.05);">
                    <div class="card-meta">
                        <span class="text-brand-cyan">LATEST INTEL</span>
                        <span>${formatTime(latestAction.time)}</span>
                    </div>
                    <div class="card-header" style="font-size: 11px;">${latestAction.title}</div>
                    <div class="card-body" style="font-size: 10px; line-height: 1.4; color: #fff;">${latestAction.content.substring(0, 150)}${latestAction.content.length > 150 ? '...' : ''}</div>
                    <div class="mt-2 flex items-center justify-between">
                         <span class="text-[9px] font-mono text-brand-dim uppercase">Score: ${latestAction.score}</span>
                         <button onclick="openFabAction('recon')" class="text-[8px] font-bold text-brand-cyan uppercase hover:underline">View All</button>
                    </div>
                </div>
            `;
        }
    } catch (err) { }
}

window.triggerManualRecon = async () => {
    const btn = get('recon-btn-mini');
    if (btn) btn.innerText = "SCANNING...";
    await fetch('/api/engine/recon', { method: 'POST' });
    setTimeout(() => {
        if (btn) btn.innerText = "SCAN";
        updateRecon();
    }, 2000);
};

async function changeGlobalConfig(type, value) {
    try {
        const res = await fetch('/api/system/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [type]: value })
        });
        const data = await res.json();
        if (data.status === 'success') {
            if (type === 'symbol') {
                get('market-symbol-title').textContent = `${value} (${get('timeframe-selector').value.toUpperCase()})`;
                if (window.initTradingView) window.initTradingView(value, get('timeframe-selector').value);
            } else {
                get('market-symbol-title').textContent = `${get('asset-selector').value} (${value.toUpperCase()})`;
                if (window.initTradingView) window.initTradingView(get('asset-selector').value, value);
            }
            syncDashboard();
        }
    } catch (e) {
        console.error("Config Sync Failed", e);
    }
}

async function toggleStrat(stratName) {
    try {
        const res = await fetch('/api/system/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strat_toggle: stratName })
        });
        const data = await res.json();
        if (data.status === 'success') {
            syncDashboard();
        }
    } catch (e) {
        console.error("Strategy Toggle Failed", e);
    }
}

function toggleActiveIntel() {
    isIntelCollapsed = !isIntelCollapsed;
    const panel = get('active-intel-panel');
    const content = get('recent-intel-content');
    const chevron = get('intel-chevron');
    const notif = get('intel-notif');

    if (isIntelCollapsed) {
        panel.style.height = "42px";
        content.style.opacity = "0";
        content.style.pointerEvents = "none";
        chevron.style.transform = "rotate(-90deg)";
    } else {
        panel.style.height = "280px";
        content.style.opacity = "1";
        content.style.pointerEvents = "auto";
        chevron.style.transform = "rotate(0deg)";
        // Mark as read when expanded
        notif.classList.add('hidden');
    }
}

function setTradeTab(cat) {
    activeTradeTab = cat;
    document.querySelectorAll('#trade-tabs-nav button[data-category]').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-category') === cat);
    });
    updateTrades();
}

async function updateTrades() {
    try {
        const endpoint = (activeTradeTab === 'OPENED') ? '/api/system/trades' : '/api/system/trades/all';
        const res = await fetch(endpoint);
        const data = await res.json();
        const container = get('trade-list');

        let trades = data.trades || [];

        // Filter if needed for 'CLOSED' on 'all' endpoint
        if (activeTradeTab === 'CLOSED') {
            trades = trades.filter(t => t.status === 'CLOSED');
        } else if (activeTradeTab === 'OPENED') {
            trades = trades.filter(t => t.status === 'OPEN');
        }

        // Filter by Strategy
        if (activeStratFilter !== 'ALL') {
            trades = trades.filter(t => {
                const strat = t.reason || "Auto";
                return strat.includes(activeStratFilter);
            });
        }

        if (trades.length === 0) {
            container.innerHTML = '<div class="card-item"><div class="card-body" style="color: var(--text-dim); text-align: center; font-size: 10px;">No trades found in this category.</div></div>';
            return;
        }

        // Grouping by Date
        const groups = {};
        trades.forEach(t => {
            const date = new Date(t.time * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
            if (!groups[date]) groups[date] = [];
            groups[date].push(t);
        });

        container.innerHTML = Object.keys(groups).sort((a, b) => new Date(b) - new Date(a)).map(date => {
            return `
                <div class="mb-6">
                    <div class="flex items-center gap-3 mb-3 px-1">
                        <div class="h-px flex-1 bg-brand-border"></div>
                        <span class="text-[8px] font-bold text-brand-dim uppercase tracking-[0.2em] whitespace-nowrap">${date}</span>
                        <div class="h-px flex-1 bg-brand-border"></div>
                    </div>
                    <div class="space-y-3">
                        ${groups[date].map(t => {
                const isClosed = t.status === 'CLOSED';
                const strategy = t.reason || 'Auto';
                const isScalp = strategy.includes('SCALP');
                const badgeColor = isScalp ? 'bg-brand-red/20 text-brand-red border-brand-red/30' : 'bg-brand-cyan/20 text-brand-cyan border-brand-cyan/30';

                return `
                            <div class="card-item ${isClosed ? 'opacity-60' : ''}">
                                <div class="card-meta">
                                    <span class="${isClosed ? 'text-brand-dim' : 'text-brand-cyan'}">${t.type}</span>
                                    <span>${formatTime(t.time)}</span>
                                </div>
                                <div class="card-header">${t.symbol} <span class="${t.pnl && t.pnl.includes('+') ? 'up' : 'down'}">${t.pnl}</span></div>
                                <div class="card-body">
                                    <div class="flex items-center justify-between mb-3 text-[10px]">
                                        <span class="text-brand-dim">Conviction: <span class="text-white">${t.conviction || 'N/A'}</span></span>
                                        <span class="text-brand-dim">Risk: <span class="${t.risk === 'HIGH' ? 'text-brand-red' : (t.risk === 'MED' ? 'text-brand-orange' : 'text-brand-green')}">${t.risk || 'UNK'}</span></span>
                                    </div>
                                    <div class="flex items-center justify-between mb-3">
                                        <span class="text-[9px] uppercase tracking-wider ${isClosed ? 'text-brand-red' : 'text-brand-green'}">${t.status}</span>
                                        <div class="flex items-center gap-1.5">
                                            <span class="px-1.5 py-0.5 rounded text-[7px] font-bold uppercase border bg-white/5 border-white/10 text-brand-dim">${t.leverage || 1}x</span>
                                            <span class="px-1.5 py-0.5 rounded text-[7px] font-bold uppercase border ${badgeColor}">${strategy}</span>
                                        </div>
                                    </div>
                                    ${!isClosed ? `<button onclick="closeTrade('${t.order_id}')" class="btn btn-approve mt-2 w-full text-[9px] bg-brand-red/10 border-brand-red/20 text-brand-red">CLOSE POSITION</button>` : ''}
                                </div>
                            </div>
                        `;
            }).join('')}
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.warn("Trade Feed Offline");
    }
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
    window.toggleOverlay = toggleOverlay;
    window.toggleReconGroup = toggleReconGroup;
    window.setLogTab = setLogTab;

    window.toggleFabMenu = (e) => {
        if (isDraggingFab) return;
        const menu = get('fab-menu');
        if (menu) menu.classList.toggle('hidden');
    };

    async function triggerDataCollect() {
        const symbol = get('hist-symbol').value;
        const interval = get('hist-interval').value;
        const start_year = parseInt(get('hist-start').value);
        const end_year = parseInt(get('hist-end').value);

        try {
            const res = await fetch('/api/data/collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, interval, start_year, end_year })
            });
            const data = await res.json();

            const container = get('file-list');
            if (container) {
                container.innerHTML = `<div class="p-4 bg-brand-cyan/10 border border-brand-cyan/20 text-brand-cyan rounded text-center mb-4 text-[10px] uppercase font-bold tracking-widest">${data.message} ${symbol}<br/>Watch System Logs for exact completion.</div>` + container.innerHTML;
            }
        } catch (e) {
            console.error("Data collection trigger failed:", e);
        }
    }

    window.openFabAction = (action) => {
        get('fab-menu').classList.add('hidden'); // Close menu after choice

        if (action === 'command') {
            get('master-command-box').classList.toggle('hidden');
        } else if (action === 'logs') {
            toggleOverlay('logs-overlay');
        } else if (action === 'files') {
            toggleOverlay('files-overlay');
        } else if (action === 'recon') {
            toggleOverlay('recon-overlay');
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

    // Click outside to close overlays
    document.querySelectorAll('.overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.classList.add('hidden');
        });
    });

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

    // Initialize Lightweight Charts (price candlestick chart)
    setTimeout(() => {
        const symbol = document.getElementById('asset-selector')?.value || 'BTCUSDT';
        const timeframe = document.getElementById('timeframe-selector')?.value || '15m';
        if (window.initTradingView) {
            window.initTradingView(symbol, timeframe);
        }
    }, 1000);

    // Refresh candlestick chart data every 30s
    setInterval(() => {
        if (window.refreshChartData) window.refreshChartData();
    }, 30000);
    setInterval(() => {
        const up = get('uptime');
        if (up) {
            const now = new Date();
            up.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        }
    }, 1000);

    // Initial State for Intelligence (Collapsed by default)
    setTimeout(() => {
        const panel = get('active-intel-panel');
        const content = get('recent-intel-content');
        const chevron = get('intel-chevron');
        if (panel && isIntelCollapsed) {
            panel.style.height = "42px";
            content.style.opacity = "0";
            content.style.pointerEvents = "none";
            chevron.style.transform = "rotate(-90deg)";
        }
    }, 500);

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
