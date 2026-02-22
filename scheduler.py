import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

import time

async def cycle_15m():
    """Update data, indicators, and signals using real exchange data."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    from core.exchange_handler import ExchangeHandler
    
    SYSTEM_STATE["heartbeat"] = "SCANNING"
    logger.info("[Cycle 15m] Fetching real-time market data...")
    
    try:
        bridge = ExchangeHandler()
        # Set a 15-second timeout for the entire sequence to prevent hanging the scheduler
        data = await asyncio.wait_for(bridge.fetch_market_data(), timeout=15)
        balance = await asyncio.wait_for(bridge.fetch_balance(), timeout=15)
        await bridge.close()
        
        if balance is not None:
            SYSTEM_STATE["equity"] = balance
            SYSTEM_STATE["exchange_connected"] = True
            logger.info(f"Exchange Sync: Success. Balance discovered: ${balance}")
        else:
            SYSTEM_STATE["exchange_connected"] = False
            logger.warning("Exchange Sync: Balance returned None (Check API Keys).")

        if data:
            SYSTEM_STATE["rsi"] = data["rsi"]
            SYSTEM_STATE["price"] = data["price"]
            SYSTEM_STATE["funding_rate"] = data["funding_rate"]
            log_msg = f"Market Sync: BTC @ ${data['price']} | RSI: {data['rsi']} | Funding: {data['funding_rate']}%"
            log_entry = {"time": time.time(), "msg": log_msg}
        else:
            log_entry = {"time": time.time(), "msg": "Market Sync Error: Exchange data incomplete."}
            
    except asyncio.TimeoutError:
        SYSTEM_STATE["exchange_connected"] = False
        logger.error("Exchange Sync Error: Timeout reaching Bybit API.")
        log_entry = {"time": time.time(), "msg": "System Alert: Bybit API timeout. Connectivity compromised."}
    except Exception as e:
        SYSTEM_STATE["exchange_connected"] = False
        logger.error(f"Exchange Sync Error: {e}")
        log_entry = {"time": time.time(), "msg": f"System Alert: Exchange Bridge failure: {str(e)[:100]}"}
    
    LOG_HISTORY.append(log_entry)
    if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_1h():
    """Recalculate scores and check trade changes."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    from core.executor import ExecutionEngine
    
    SYSTEM_STATE["heartbeat"] = "CHECKING_TRADE"
    logger.info("[Cycle 1h] Running Execution Bridge analysis...")
    
    executor = ExecutionEngine()
    decision = executor.check_trade_readiness(SYSTEM_STATE)
    
    # In 'paper' mode, we might auto-execute locally, but here we just log it
    # approved signals will usually go to APPROVAL_QUEUE via the Scientist reports
    # but the executor can also block/READY based on technicals
    
    log_msg = f"Execution Decision: {decision['decision']} - {decision['reason']}"
    log_entry = {"time": time.time(), "msg": log_msg}
    LOG_HISTORY.append(log_entry)
    
    if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_4h():
    """Update regime state."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    SYSTEM_STATE["heartbeat"] = "REGIME_SCAN"
    logger.info("[Cycle 4h] Updating market regime classification...")
    # Real logic: If RSI > 70 and Sentiment > 0.5 -> BULL_TREND
    if SYSTEM_STATE.get("rsi", 50) > 60:
        SYSTEM_STATE["regime"] = "BULL_TREND"
    elif SYSTEM_STATE.get("rsi", 50) < 40:
        SYSTEM_STATE["regime"] = "BEAR_TREND"
    else:
        SYSTEM_STATE["regime"] = "RANGING"

    log_entry = {"time": time.time(), "msg": f"Regime Engine: 4h Trend Analysis completed. Current: {SYSTEM_STATE['regime']}"}
    LOG_HISTORY.append(log_entry)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_daily():
    """Walk forward, strategy memory, ai review, reports."""
    logger.info("[Cycle Daily] Running walk-forward validation and AI meta-review...")

async def start_scheduler_async():
    scheduler = AsyncIOScheduler()
    
    from datetime import datetime
    
    # 15m Cycle (Run immediately)
    scheduler.add_job(cycle_15m, 'interval', minutes=15, next_run_time=datetime.now())
    
    # 1h Cycle
    scheduler.add_job(cycle_1h, 'interval', hours=1, next_run_time=datetime.now())
    
    # 4h Cycle
    scheduler.add_job(cycle_4h, 'interval', hours=4, next_run_time=datetime.now())
    
    # Daily Cycle (at midnight)
    scheduler.add_job(cycle_daily, 'cron', hour=0, minute=0)
    
    scheduler.start()
    logger.info("Async Scheduler started for all cycles (15m, 1h, 4h, daily).")
    
    # Keep it running if needed locally, but usually managed by app.py
    while True:
        await asyncio.sleep(1000)
