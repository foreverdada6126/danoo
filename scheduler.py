import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

import time

async def cycle_15m():
    """Update data, indicators, and signals."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    SYSTEM_STATE["heartbeat"] = "SCANNING"
    logger.info("[Cycle 15m] Fetching new candles and updating indicator state...")
    await asyncio.sleep(2) # Simulate work
    log_entry = {"time": time.strftime("%H:%M:%S"), "msg": "Strategy Scan: Indicators recalculated for BTC/USDT."}
    LOG_HISTORY.append(log_entry)
    if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_1h():
    """Recalculate scores and check trade changes."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    SYSTEM_STATE["heartbeat"] = "BACKTESTING"
    logger.info("[Cycle 1h] Recalculating strategy scores and trade state...")
    await asyncio.sleep(3) # Simulate refinement
    log_entry = {"time": time.strftime("%H:%M:%S"), "msg": "Cycle 1h: Walk-forward testing active strategies..."}
    LOG_HISTORY.append(log_entry)
    if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_4h():
    """Update regime state."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    SYSTEM_STATE["heartbeat"] = "REGIME_SCAN"
    logger.info("[Cycle 4h] Updating market regime classification...")
    await asyncio.sleep(5) # Simulate analysis
    log_entry = {"time": time.strftime("%H:%M:%S"), "msg": "Regime Engine: 4h Trend Analysis completed."}
    LOG_HISTORY.append(log_entry)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_daily():
    """Walk forward, strategy memory, ai review, reports."""
    logger.info("[Cycle Daily] Running walk-forward validation and AI meta-review...")

async def start_scheduler_async():
    scheduler = AsyncIOScheduler()
    
    # 15m Cycle
    scheduler.add_job(cycle_15m, 'interval', minutes=15)
    
    # 1h Cycle
    scheduler.add_job(cycle_1h, 'interval', hours=1)
    
    # 4h Cycle
    scheduler.add_job(cycle_4h, 'interval', hours=4)
    
    # Daily Cycle (at midnight)
    scheduler.add_job(cycle_daily, 'cron', hour=0, minute=0)
    
    scheduler.start()
    logger.info("Async Scheduler started for all cycles (15m, 1h, 4h, daily).")
    
    # Keep it running if needed locally, but usually managed by app.py
    while True:
        await asyncio.sleep(1000)
