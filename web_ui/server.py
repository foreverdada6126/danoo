"""
DaNoo Web UI Server - Slim Orchestrator.
All routes are split into modular files under web_ui/routes/.
Shared state lives in web_ui/state.py.
"""
import os
import time
import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from database.models import DB_SESSION, Trade

# ─── Import Shared State ─────────────────────────────────────────
from web_ui.state import (
    SYSTEM_STATE, LOG_HISTORY, RECON_HISTORY,
    ACTIVE_TRADES, APPROVAL_QUEUE, EQUITY_HISTORY,
    PREDICTION_STATE
)

# ─── Boot: Load Historical Logs ──────────────────────────────────
def load_log_file():
    """Initializes LOG_HISTORY with the last entries from the log file."""
    log_file = "logs/engine.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()[-100:]
                for line in lines:
                    parts = line.strip().split(" | ")
                    if len(parts) >= 3:
                        raw_msg = parts[-1]
                        level = parts[1].strip() if len(parts) > 1 else "INFO"
                        cat = "CORE"
                        if any(x in raw_msg.upper() for x in ["SYNC", "MARKET", "PRICE", "RSI"]):
                            cat = "EXCH"
                        if any(x in raw_msg.upper() for x in ["ORDER", "TRADE", "CLOSED", "PNL"]):
                            cat = "TRADE"
                        if level in ["ERROR", "CRITICAL", "WARNING"]:
                            cat = "ERR"
                        LOG_HISTORY.append({
                            "time": time.time(),
                            "msg": f"[{level}] {raw_msg}",
                            "cat": cat
                        })
        except Exception as e:
            logger.error(f"Failed to load historical logs: {e}")

load_log_file()

# ─── Boot: Load Open Trades from DB ──────────────────────────────
def load_persistence():
    """Loads previous session state from SQLite."""
    from web_ui.state import TRADE_LOG_HISTORY
    try:
        session = DB_SESSION()
        # 1. Load Active Trades
        trades = session.query(Trade).filter(Trade.status == 'OPEN').all()
        for t in trades:
            ACTIVE_TRADES.append({
                "id": t.id,
                "time": t.entry_time.timestamp(),
                "symbol": t.symbol,
                "type": f"{t.side.upper()} ({t.strategy.split('_')[0] if t.strategy else 'MANUAL'})",
                "status": t.status,
                "pnl": f"${t.pnl:.2f}" if t.pnl else "$0.00",
                "order_id": t.order_id,
                "reason": t.strategy or "Persistent Trade",
                "leverage": t.leverage or 1
            })
            
        # 2. Re-hydrate Trade Log History with last 20 events
        history = session.query(Trade).order_by(Trade.id.desc()).limit(20).all()
        for h in reversed(history):
            # Add Entry Event
            TRADE_LOG_HISTORY.append({
                "timestamp": h.entry_time.timestamp(),
                "action": "ENTRY",
                "symbol": h.symbol,
                "type": h.side,
                "price": h.entry_price,
                "amount": h.amount,
                "leverage": h.leverage or 1,
                "reason": h.strategy
            })
            # Add Exit Event if closed
            if h.status == "CLOSED" and h.exit_time:
                TRADE_LOG_HISTORY.append({
                    "timestamp": h.exit_time.timestamp(),
                    "action": "EXIT",
                    "symbol": h.symbol,
                    "type": h.side,
                    "price": h.exit_price,
                    "amount": h.amount,
                    "leverage": h.leverage or 1,
                    "pnl": h.pnl,
                    "pnl_pct": ((h.exit_price - h.entry_price) / h.entry_price * 100 * (1 if h.side == "BUY" else -1)) if h.entry_price else 0,
                    "reason": "Persistence Recovery"
                })
        
        logger.info(f"Database: Loaded {len(ACTIVE_TRADES)} active and {len(TRADE_LOG_HISTORY)} historical events.")
        session.close()
    except Exception as e:
        logger.error(f"Persistence Load Error: {e}")

load_persistence()

# ─── Real-time Log Bridge ────────────────────────────────────────
def ui_log_sink(message):
    """Pushes every logger call into the Dashboard UI."""
    try:
        record = message.record
        msg_text = record["message"]
        level = record["level"].name
        
        cat = "CORE"
        if any(x in msg_text.upper() for x in ["SYNC", "MARKET", "PRICE", "RSI", "FUNDING", "TICKER"]):
            cat = "EXCH"
        if any(x in msg_text.upper() for x in ["ORDER", "TRADE", "CLOSED", "ENTRY", "PNL", "FILLED", "POSITION"]):
            cat = "TRADE"
        if level in ["ERROR", "CRITICAL", "WARNING"] or "ALERT" in msg_text.upper() or "FAILURE" in msg_text.upper():
            cat = "ERR"
            
        log_entry = {
            "time": time.time(),
            "msg": f"[{level}] {msg_text}",
            "cat": cat
        }
        LOG_HISTORY.append(log_entry)
        if len(LOG_HISTORY) > 1000: LOG_HISTORY.pop(0)
    except:
        pass

_UI_SINK_ADDED = False
if not globals().get("_UI_SINK_ADDED", False):
    logger.add(ui_log_sink, format="{message}", level="DEBUG")
    globals()["_UI_SINK_ADDED"] = True

# ─── Host Metrics Path (Docker) ──────────────────────────────────
os.environ["PROCFS_PATH"] = "/host/proc"

# ─── FastAPI App ─────────────────────────────────────────────────
app = FastAPI(title="DaNoo - Strategy Intelligence Engine v5.2")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="web_ui/static"), name="static")
templates = Jinja2Templates(directory="web_ui/templates")

# ─── Register Route Modules ─────────────────────────────────────
from web_ui.routes.status import router as status_router
from web_ui.routes.trades import router as trades_router
from web_ui.routes.charts import router as charts_router
from web_ui.routes.admin import router as admin_router

app.include_router(status_router)
app.include_router(trades_router)
app.include_router(charts_router)
app.include_router(admin_router)

# ─── Root Page ───────────────────────────────────────────────────
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "state": SYSTEM_STATE})

# ─── Server Factory ─────────────────────────────────────────────
import uvicorn

def start_ui_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    return server
