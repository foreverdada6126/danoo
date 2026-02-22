import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

import time
import pandas as pd
from core.scalper_engine import ScalperEngine
from core.strategy_library import StrategyLibrary
from config.settings import SETTINGS

# Initialize Scalper
SCALPER = ScalperEngine()

async def cycle_15m():
    """Background Intelligence Scan for all assets in the Watchlist."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY, RECON_HISTORY
    from core.exchange_handler import ExchangeHandler
    
    SYSTEM_STATE["heartbeat"] = "SCANNING_ALL"
    logger.info(f"[Cycle 15m] Comprehensive Watchlist Scan: {len(SETTINGS.WATCHLIST)} assets")
    
    bridge = ExchangeHandler()
    
    for symbol in SETTINGS.WATCHLIST:
        try:
            client = await bridge._get_client()
            ohlcv = await client.fetch_ohlcv(symbol, "15m", limit=30)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            rsi_vals = StrategyLibrary.calculate_rsi(df['close'].values, 14)
            rsi = rsi_vals[-1]
            price = df['close'].iloc[-1]
            
            if symbol == SETTINGS.DEFAULT_SYMBOL:
                SYSTEM_STATE["rsi"] = rsi
                SYSTEM_STATE["price"] = price
                SYSTEM_STATE["exchange_connected"] = True
            
            # Mission Intelligence Log (Recon)
            report_time = time.time()
            RECON_HISTORY.append({
                "time": report_time,
                "title": f"AUTO-SCAN: {symbol}",
                "content": f"Automated background research complete for {symbol}. \nPrice: ${price:.4f} \nRSI: {rsi:.2f} \nTrend: { 'BULLISH' if rsi > 50 else 'BEARISH' }",
                "score": round((rsi - 50) / 50, 2)
            })
            if len(RECON_HISTORY) > 50: RECON_HISTORY.pop(0)
            
        except Exception as e:
            logger.error(f"Intelligence Scan Failed for {symbol}: {e}")

    # General Balance Update
    try:
        balance = await bridge.fetch_balance()
        if balance is not None:
            SYSTEM_STATE["equity"] = balance
            SYSTEM_STATE["exchange_connected"] = True
            if balance == 0 and not SETTINGS.BYBIT_API_KEY:
                logger.warning("Exchange Bridge: Connected in PAPER mode (No API Keys).")
            else:
                logger.info(f"Exchange Bridge: Connection Verified. Wallet: ${balance}")
        else:
            SYSTEM_STATE["exchange_connected"] = False
            logger.error("Exchange Bridge: Connection Failed (Balance returned None).")
    except Exception as e:
        SYSTEM_STATE["exchange_connected"] = False
        logger.error(f"Exchange Bridge: Fatal Connection Error: {e}")
    
    await bridge.close()
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_1h():
    """Recalculate scores and check trade changes."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    from core.executor import ExecutionEngine
    
    SYSTEM_STATE["heartbeat"] = "CHECKING_TRADE"
    logger.info("[Cycle 1h] Running Execution Bridge analysis...")
    
    executor = ExecutionEngine()
    decision = executor.check_trade_readiness(SYSTEM_STATE)
    
    log_msg = f"Execution Decision: {decision['decision']} - {decision['reason']}"
    log_entry = {"time": time.time(), "msg": log_msg}
    LOG_HISTORY.append(log_entry)
    
    if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_4h():
    """Update regime state using full RegimeEngine analysis."""
    from web_ui.server import SYSTEM_STATE, LOG_HISTORY
    from core.exchange_handler import ExchangeHandler
    from core.regime_engine import RegimeEngine
    
    SYSTEM_STATE["heartbeat"] = "REGIME_SCAN"
    logger.info("[Cycle 4h] Running full market regime classification...")
    
    try:
        bridge = ExchangeHandler()
        client = await bridge._get_client()
        ohlcv = await client.fetch_ohlcv(SETTINGS.DEFAULT_SYMBOL, "4h", limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        await bridge.close()
        
        regime_engine = RegimeEngine()
        regime = regime_engine.analyze(df)
        weights = regime_engine.get_regime_weights(regime)
        
        SYSTEM_STATE["regime"] = regime
        SYSTEM_STATE["regime_weights"] = weights
        
        log_entry = {"time": time.time(), "msg": f"Regime Engine: 4h Analysis complete. Regime: {regime} | Weights: VolExp={weights.get('VolatilityExpansion', 1.0):.1f}, MR={weights.get('MeanReversion', 1.0):.1f}, Mom={weights.get('Momentum', 1.0):.1f}"}
    except Exception as e:
        logger.error(f"Regime analysis failed: {e}")
        if SYSTEM_STATE.get("rsi", 50) > 60:
            SYSTEM_STATE["regime"] = "BULL_TREND"
        elif SYSTEM_STATE.get("rsi", 50) < 40:
            SYSTEM_STATE["regime"] = "BEAR_TREND"
        else:
            SYSTEM_STATE["regime"] = "RANGING"
        log_entry = {"time": time.time(), "msg": f"Regime Engine: Fallback RSI classification. Current: {SYSTEM_STATE['regime']}"}
    
    LOG_HISTORY.append(log_entry)
    SYSTEM_STATE["heartbeat"] = "IDLE"

async def cycle_scalp_1m():
    """High-frequency scalper loop."""
    await SCALPER.scan_market()

async def cycle_daily():
    """Walk forward, strategy memory, ai review, reports."""
    logger.info("[Cycle Daily] Running walk-forward validation and AI meta-review...")

async def start_scheduler_async():
    scheduler = AsyncIOScheduler()
    from datetime import datetime
    
    # 15m Cycle (Run immediately)
    scheduler.add_job(cycle_15m, 'interval', minutes=15, next_run_time=datetime.now())
    
    # 1m Scalper Cycle
    scheduler.add_job(cycle_scalp_1m, 'interval', minutes=1, next_run_time=datetime.now())
    
    # 1h Cycle
    scheduler.add_job(cycle_1h, 'interval', hours=1, next_run_time=datetime.now())
    
    # 4h Cycle
    scheduler.add_job(cycle_4h, 'interval', hours=4, next_run_time=datetime.now())
    
    # Daily Cycle (at midnight)
    scheduler.add_job(cycle_daily, 'cron', hour=0, minute=0)
    
    scheduler.start()
    logger.info("Async Scheduler started for institutional watchlist cycles.")
    
    while True:
        await asyncio.sleep(1000)
