"""
Adaptive Strategy Intelligence Engine v5.4 - Main Orchestrator
"""
import asyncio
import sys
import os
import time
from loguru import logger
from config.settings import SETTINGS
from core.regime_engine import RegimeEngine
from telegram_bot.bot import TelegramBot
from scheduler import start_scheduler_async
from web_ui.server import start_ui_server
from web_ui.state import SYSTEM_STATE, LOG_HISTORY, PREDICTION_STATE
from core.prediction_engine import PredictionEngine
predictor = PredictionEngine()

import httpx

async def run_market_intelligence(bot):
    """Periodically call intel-service for AI-driven sentiment analysis."""
    while True:
        try:
            # 0. Check Power Toggle
            if not SYSTEM_STATE.get("ai_active", True):
                logger.info("Intelligence Loop: AI Communication is disabled. Scanning bypassed.")
                await asyncio.sleep(300) # Check again in 5 mins
                continue
                
            # 1. Fetch data from Intel Service
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://intel-service:5000/api/research/analyze",
                    json={
                        "query": f"Analyze current regime for {SYSTEM_STATE['symbol']}",
                        "context": f"Regime: {SYSTEM_STATE['regime']}, Trend: {SYSTEM_STATE['trend']}"
                    },
                    timeout=30.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    analysis = data.get("analysis", "No analysis returned.")
                    
                    # 2. Update Dashboard State
                    SYSTEM_STATE["ai_insight"] = analysis[:200] + "..."
                    
                    # Try to extract sentiment if the AI followed the pipe format
                    sentiment = 0.0
                    if "|" in analysis:
                        try:
                            parts = analysis.split("|")
                            if len(parts) >= 2:
                                import re
                                score_clean = re.findall(r"[-+]?\d*\.\d+|\d+", parts[-2])[0]
                                sentiment = float(score_clean)
                        except: pass
                    
                    SYSTEM_STATE["sentiment_score"] = sentiment
                    logger.success("Intelligence Review Completed and Synced to Core.")
                    
        except Exception as e:
            logger.error(f"Intelligence Task Error: {e}")
            # If it's a connection error, retry much faster than 1 hour
            await asyncio.sleep(30)
            continue
        
        await asyncio.sleep(3600) # Run every hour

async def run_prediction_engine():
    """Background task to update market forecasts with priority for the active asset."""
    from core.exchange_handler import ExchangeHandler
    logger.info("Prediction Engine: Background Loop Started with Prioritization.")
    while True:
        try:
            timeframe = SYSTEM_STATE.get("timeframe", "15m")
            bridge = ExchangeHandler()
            client = await bridge._get_client(force_public=True)
            
            # 1. Prioritize Current Asset
            current_fav = SYSTEM_STATE.get("symbol", "BTCUSDT")
            targets = [current_fav] + [s for s in SETTINGS.WATCHLIST if s != current_fav]
            
            for symbol in targets:
                try:
                    # Skip if we already have fresh data (within last 2 mins) for background assets
                    if symbol != current_fav:
                        last_pred = PREDICTION_STATE.get(symbol)
                        if last_pred and (time.time() - last_pred.get('timestamp', 0)) < 120:
                            continue

                    logger.info(f"Prediction Engine: Processing {symbol}...")
                    ohlcv = await client.fetch_ohlcv(symbol, timeframe, limit=300)
                    
                    if len(ohlcv) < 50: continue
                        
                    from web_ui.state import LIQUIDITY_STATE
                    liq_data = LIQUIDITY_STATE.get(symbol)
                    forecast = await predictor.train_and_predict(symbol, ohlcv, liquidity_data=liq_data)
                    
                    if forecast:
                        PREDICTION_STATE[symbol] = forecast
                        if symbol == current_fav:
                            backing = "💎" if forecast.get('institutional_backed') else "📈"
                            logger.success(f"EXPERT SYNC: {backing} {symbol} -> {forecast['direction']} ({forecast['change_pct']}%)")
                except Exception as asset_err:
                    logger.error(f"Prediction Engine Error [{symbol}]: {asset_err}")
                
                await asyncio.sleep(1) # Faster rotation
            
        except Exception as e:
            logger.error(f"Prediction Engine Main Loop Error: {e}")
            
        await asyncio.sleep(60) # Faster cycle check

async def run_liquidity_engine():
    """Institutional Order Book Depth Scan - Running in background."""
    from core.liquidity_scanner import LIQUIDITY_SCANNER
    from web_ui.state import LIQUIDITY_STATE
    logger.info("Order Book Intelligence: Deep Depth Engine Started.")
    while True:
        try:
            current_fav = SYSTEM_STATE.get("symbol", "BTCUSDT")
            targets = [current_fav] + [s for s in SETTINGS.WATCHLIST if s != current_fav]
            
            for symbol in targets:
                scan = await LIQUIDITY_SCANNER.scan_symbol(symbol)
                if scan:
                    LIQUIDITY_STATE[symbol] = scan
                    if symbol == current_fav:
                        logger.info(f"[Liquidity] {symbol} Walls found: Bids={scan['bid_walls']}, Asks={scan['ask_walls']} | Imbalance: {scan['imbalance']}")
                await asyncio.sleep(1) # Fast depth rotation
                
        except Exception as e:
            logger.error(f"Liquidity Engine Error: {e}")
        await asyncio.sleep(1) # High-frequency refresh

async def main():
    logger.add("logs/engine.log", rotation="10 MB", level="INFO")
    SYSTEM_STATE["version"] = SETTINGS.VERSION # Force sync
    logger.info(f"Initializing {SETTINGS.PROJECT_NAME} v{SETTINGS.VERSION}...")
    logger.success("--- SYSTEM PATCH v5.5.0 ACTIVE (EXPERT MODE) ---")
    
    try:
        # 1. Initialize Telegram Bot (Core UI)
        logger.info("Pillar 1/6: Initializing Telegram Interface...")
        bot = TelegramBot()
        await bot.start_bot()
        await bot.send_alert(f"🚀 DaNoo v{SETTINGS.VERSION} Expert Mode Online.")
        
        # 2. Start Web UI Server (Background Task)
        logger.info("Pillar 2/6: Initializing Command Hub Server...")
        ui_server = start_ui_server()
        asyncio.create_task(ui_server.serve())
        
        # 3. Start Intelligence Task
        logger.info("Pillar 3/6: Spawning Intelligence Watchdog...")
        asyncio.create_task(run_market_intelligence(bot))
        
        # 4. Start ML Prediction Engine
        logger.info("Pillar 4/6: Spawning Prediction Engine...")
        asyncio.create_task(run_prediction_engine())
        
        # 5. Start Institutional Liquidity Engine
        logger.info("Pillar 5/6: Spawning Liquidity Sniper...")
        asyncio.create_task(run_liquidity_engine())
        
        # 6. Initialize Execution & Scalper
        logger.info("Pillar 6/6: Calibration of Execution Engines...")
        regime_engine = RegimeEngine()
        
        # 5. Start Routine Orchestration (Scheduler)
        logger.info("Pillar 5/5: Starting Scheduler Orchestrator...")
        asyncio.create_task(start_scheduler_async())
        
        # 6. Immediate Sync for UI
        from scheduler import cycle_15m
        asyncio.create_task(cycle_15m())
        
        # 7. Initial System Log
        logger.info("INITIALIZATION COMPLETE. System is now fully autonomous.")
        
        # Keep the main process alive
        while True:
            await asyncio.sleep(60)
            
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    except Exception as e:
        logger.error(f"CRITICAL SYSTEM ERROR during boot: {e}")
        # Send alert if possible
        try: await bot.send_alert(f"⚠️ CRITICAL: DaNoo Engine crashed during boot: {e}")
        except: pass
    finally:
        logger.info("Clean shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
