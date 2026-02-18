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
        document.getElementById('meta-symbol').textContent = data.symbol;
        document.getElementById('meta-trend').textContent = data.trend;
        document.getElementById('meta-rsi').textContent = data.rsi;
        document.getElementById('meta-tf').textContent = data.timeframe;
    } catch (e) { console.error("Update failed"); }
}

// Initialization
initChart();
loadChartData();
updateLogs();
setInterval(updateState, 5000);
setInterval(updateLogs, 10000);

setInterval(() => {
    document.getElementById('uptime').textContent = new Date().toLocaleTimeString();
}, 1000);
