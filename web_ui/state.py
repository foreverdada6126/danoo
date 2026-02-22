"""
Centralized State Management for DaNoo.
All shared state containers live here to eliminate circular imports.
"""
import time
from config.settings import SETTINGS

# ─── Core System State ───────────────────────────────────────────
SYSTEM_STATE = {
    "status": "OPERATIONAL",
    "mode": SETTINGS.MODE.upper(),
    "exchange_id": SETTINGS.EXCHANGE_ID.upper(),
    "exchange_connected": False,
    "regime": "RANGING",
    "equity": 5000.0 if SETTINGS.MODE == "paper" else 0.0,
    "pnl_24h": 0.0,
    "active_orders": 0,
    "symbol": "BTCUSDT",
    "trend": "NEUTRAL",
    "rsi": 45.2,
    "timeframe": "15m",
    "ai_insight": "Awaiting initial research...",
    "sentiment_score": 0.0,
    "price": 0.0,
    "funding_rate": 0.0,
    "heartbeat": "IDLE",
    "ai_active": True,
    "strat_strict": True,
    "strat_loose": True,
    "strat_recon": True
}

# Per-Asset State Tracking (Equity/PNL)
ASSET_STATE = {}
PREDICTION_STATE = {}

# ─── Data Containers ─────────────────────────────────────────────
LOG_HISTORY = []
RECON_HISTORY = []
ACTIVE_TRADES = []
APPROVAL_QUEUE = []
EQUITY_HISTORY = []
TRADE_LOG_HISTORY = [] # Detailed trade execution logs
INTELLIGENCE_FLOW = [] # Real-time flow of chart data, signals, and engine heartbeats
