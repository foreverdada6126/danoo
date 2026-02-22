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
        
async def run_prediction_engine():
    """Background task to update market forecasts every 5 minutes."""
    from core.exchange_handler import ExchangeHandler
    logger.info("Prediction Engine: Background Loop Started.")
    while True:
        try:
            current_symbol = SYSTEM_STATE.get("symbol", "BTCUSDT")
            timeframe = SYSTEM_STATE.get("timeframe", "15m")
            
            logger.info(f"Prediction Engine: Updating Forecast for {current_symbol}...")
            bridge = ExchangeHandler()
            client = await bridge._get_client(force_public=True)
            ohlcv = await client.fetch_ohlcv(current_symbol, timeframe, limit=300)
            
            logger.info(f"Prediction Engine: Data Ingested ({len(ohlcv)} candles). Training...")
            forecast = await predictor.train_and_predict(current_symbol, ohlcv)
            if forecast:
                # Update global prediction state
                PREDICTION_STATE[current_symbol] = forecast
                logger.success(f"Prediction Engine: Forecast Update for {current_symbol} -> {forecast['direction']} ({forecast['change_pct']}%). Confidence: {forecast['confidence']}%")
            
        except Exception as e:
            logger.error(f"Prediction Engine Error: {e}")
            
        await asyncio.sleep(300) # Every 5 minutes

async def main():
    logger.add("logs/engine.log", rotation="10 MB", level="INFO")
    logger.info(f"Initializing {SETTINGS.PROJECT_NAME} v{SETTINGS.VERSION}...")
    logger.success("--- SYSTEM PATCH v5.4.1 ACTIVE (PERFORMANCE MODE) ---")
    
    try:
        # 1. Initialize Telegram Bot (Core UI)
        logger.info("Pillar 1/5: Initializing Telegram Interface...")
        bot = TelegramBot()
        await bot.start_bot()
        await bot.send_alert(f"🚀 DaNoo v5.4 Engine Online. Version 5.4.1 Patched.")
        
        # 2. Start Web UI Server (Background Task)
        logger.info("Pillar 2/5: Initializing Command Hub Server...")
        ui_server = start_ui_server()
        asyncio.create_task(ui_server.serve())
        logger.info("Web UI Server status: LIVE on http://0.0.0.0:8000")
        
        # 3. Start Intelligence Task
        logger.info("Pillar 3/5: Spawning Intelligence Watchdog...")
        asyncio.create_task(run_market_intelligence(bot))
        
        # 3.5 Start Prediction Task
        logger.info("Pillar 3.1/5: Spawning Prediction Engine...")
        asyncio.create_task(run_prediction_engine())
        
        # 4. Initialize Internal Engines
        logger.info("Pillar 4/5: Calibration of Regime & Execution Engines...")
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
