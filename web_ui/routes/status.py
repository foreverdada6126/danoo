"""
Status & System Routes - Health, status, system info, reports.
"""
import time
import psutil
import platform
import subprocess
from fastapi import APIRouter
from loguru import logger
from web_ui.state import SYSTEM_STATE, LOG_HISTORY, ACTIVE_TRADES

router = APIRouter()

@router.get("/api/status")
async def get_status():
    """Returns the core system state (equity, regime, insights)."""
    from database.models import DB_SESSION, Trade
    from datetime import datetime, timedelta
    from core.exchange_handler import ExchangeHandler
    from web_ui.state import ASSET_STATE
    
    SYSTEM_STATE["active_orders"] = len(ACTIVE_TRADES)
    current_symbol = SYSTEM_STATE.get("symbol", "BTCUSDT")
    
    try:
        session = DB_SESSION()
        
        # Global Trade counts
        SYSTEM_STATE["trades_total"] = session.query(Trade).count()
        SYSTEM_STATE["trades_open"] = session.query(Trade).filter(Trade.status == 'OPEN').count()
        SYSTEM_STATE["trades_closed"] = session.query(Trade).filter(Trade.status == 'CLOSED').count()
        
        # --- Per-Asset Calculation ---
        # 1. Realized PnL (Last 24h for current asset)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_closed = session.query(Trade).filter(
            Trade.symbol == current_symbol,
            Trade.status == 'CLOSED',
            Trade.exit_time >= cutoff
        ).all()
        realized_pnl = sum((t.pnl or 0.0) for t in recent_closed)
        
        # 2. Unrealized PnL (Current open trades for asset)
        unrealized_pnl = 0.0
        open_trades = session.query(Trade).filter(
            Trade.symbol == current_symbol,
            Trade.status == 'OPEN'
        ).all()
        
        if open_trades:
            # Fetch current price
            try:
                bridge = ExchangeHandler()
                client = await bridge._get_client()
                ticker = await client.fetch_ticker(current_symbol)
                current_price = ticker.get("last", 0.0)
                await bridge.close()
            except:
                current_price = SYSTEM_STATE.get("price", 0.0)
            
            if current_price > 0:
                for t in open_trades:
                    if t.entry_price and t.amount:
                        side_mult = 1 if t.side.upper() in ["BUY", "LONG"] else -1
                        unrealized_pnl += (current_price - t.entry_price) * t.amount * side_mult
        
        # 3. Update ASSET_STATE
        if current_symbol not in ASSET_STATE:
            ASSET_STATE[current_symbol] = {
                "initial_equity": 5000.0 if SYSTEM_STATE["mode"] == "PAPER" else 0.0,
                "cumulative_pnl": 0.0
            }
        
        # Get total realized PnL for this asset (all time) to calculate total equity
        all_closed = session.query(Trade).filter(
            Trade.symbol == current_symbol,
            Trade.status == 'CLOSED'
        ).all()
        total_realized = sum((t.pnl or 0.0) for t in all_closed)
        
        current_equity = ASSET_STATE[current_symbol]["initial_equity"] + total_realized + unrealized_pnl
        SYSTEM_STATE["equity"] = current_equity
        SYSTEM_STATE["pnl_24h"] = realized_pnl + unrealized_pnl
        
        session.close()
    except Exception as e:
        logger.error(f"Status Calculation Error: {e}")
    
    return SYSTEM_STATE

@router.get("/api/trade_logs")
async def get_trade_logs():
    """Returns specialized logs for chart trade actions."""
    from web_ui.state import TRADE_LOG_HISTORY
    return {"logs": TRADE_LOG_HISTORY}

@router.get("/api/system/health")
async def get_health():
    """Returns VPS health metrics."""
    return {
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "ram_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime": int(time.time() - psutil.boot_time()),
        "platform": platform.system()
    }

@router.get("/api/system/info")
async def get_system_info():
    """Returns version and git status."""
    from config.settings import SETTINGS
    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
        git_msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"]).decode().strip()
    except:
        git_hash = "no-git"
        git_msg = "Unknown"
    return {
        "version": SETTINGS.VERSION,
        "git_hash": git_hash,
        "last_commit": git_msg,
        "mode": SETTINGS.MODE
    }

@router.get("/api/system/report")
async def get_system_report():
    """Executes system commands for a full report."""
    try:
        cpu = subprocess.check_output(["top", "-bn1"]).decode().split('\n')[2]
        mem = subprocess.check_output(["free", "-h"]).decode()
        disk = subprocess.check_output(["df", "-h", "/"]).decode()
        containers = subprocess.check_output(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"]).decode()
        report = f"--- CPU VITAL ---\n{cpu}\n\n--- MEMORY VITAL ---\n{mem}\n--- DISK VITAL ---\n{disk}\n--- CONTAINER FLEET ---\n{containers}"
        return {"report": report}
    except Exception as e:
        return {"report": f"Report Generation Error: {str(e)}"}

@router.get("/api/logs")
async def get_logs():
    return LOG_HISTORY

@router.post("/api/system/cleanup")
async def run_cleanup():
    """Performs basic housekeeping (clearing logs)."""
    try:
        LOG_HISTORY.clear()
        LOG_HISTORY.append({"time": time.time(), "msg": "Housekeeping: Logs cleared."})
        return {"status": "success", "message": "Housekeeping complete. Logs cleared."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
