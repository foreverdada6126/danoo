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
        from config.settings import SETTINGS
        watchlist = SETTINGS.WATCHLIST
        
        total_equity = 0.0
        total_pnl_24h = 0.0
        
        asset_equity = 0.0
        asset_pnl_24h = 0.0
        
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        # Calculate per asset
        for symbol in watchlist:
            # 1. Realized 24h PnL
            recent_closed = session.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == 'CLOSED',
                Trade.exit_time >= cutoff
            ).all()
            realized_24h = sum((t.pnl or 0.0) for t in recent_closed)
            
            # 2. Cumulative Realized PnL (all time)
            all_closed = session.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == 'CLOSED'
            ).all()
            total_realized = sum((t.pnl or 0.0) for t in all_closed)
            
            # 3. Unrealized PnL
            unrealized_pnl = 0.0
            open_trades = session.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == 'OPEN'
            ).all()
            
            if open_trades:
                try:
                    bridge = ExchangeHandler()
                    client = await bridge._get_client(force_public=True)
                    ticker = await client.fetch_ticker(symbol)
                    p = ticker.get("last", 0.0)
                except:
                    p = SYSTEM_STATE.get("price", 0.0) if symbol == current_symbol else 0.0
                
                if p > 0:
                    for t in open_trades:
                        if t.entry_price and t.amount:
                            side_mult = 1 if t.side.upper() in ["BUY", "LONG"] else -1
                            unrealized_pnl += (p - t.entry_price) * t.amount * side_mult
            
            # 4. State Calculation
            initial_equity = 1000.0 if SYSTEM_STATE.get("mode") == "PAPER" else 0.0
            current_asset_equity = initial_equity + total_realized + unrealized_pnl
            current_asset_pnl_24h = realized_24h + unrealized_pnl
            
            total_equity += current_asset_equity
            total_pnl_24h += current_asset_pnl_24h
            
            if symbol == current_symbol:
                asset_equity = current_asset_equity
                asset_pnl_24h = current_asset_pnl_24h
                SYSTEM_STATE["trades_total"] = session.query(Trade).filter(Trade.symbol == current_symbol).count()
                SYSTEM_STATE["trades_open"] = session.query(Trade).filter(Trade.status == 'OPEN', Trade.symbol == current_symbol).count()
                SYSTEM_STATE["trades_closed"] = session.query(Trade).filter(Trade.status == 'CLOSED', Trade.symbol == current_symbol).count()
                
            # Internal state tracking
            if symbol not in ASSET_STATE:
                ASSET_STATE[symbol] = {"initial_equity": initial_equity, "cumulative_pnl": 0.0}
        
        SYSTEM_STATE["total_equity"] = total_equity
        SYSTEM_STATE["total_pnl_24h"] = total_pnl_24h
        SYSTEM_STATE["asset_equity"] = asset_equity
        SYSTEM_STATE["asset_pnl_24h"] = asset_pnl_24h
        
        # Legacy support
        SYSTEM_STATE["equity"] = total_equity
        SYSTEM_STATE["pnl_24h"] = total_pnl_24h
        
        session.close()
    except Exception as e:
        import traceback
        logger.error(f"Status Calculation Error: {e}\n{traceback.format_exc()}")
    
    return SYSTEM_STATE

@router.get("/api/intelligence/flow")
async def get_intel_flow():
    """Returns real-time flow of chart data, signals, and engine heartbeats."""
    from web_ui.state import INTELLIGENCE_FLOW
    return {"flow": INTELLIGENCE_FLOW}

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
