"""
Adaptive Strategy Intelligence Engine v5.2 - Main Orchestrator
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
from web_ui.server import start_ui_server, SYSTEM_STATE, LOG_HISTORY

import httpx

async def run_market_intelligence(bot):
    """Periodically call intel-service for AI-driven sentiment analysis."""
    while True:
        try:
            from web_ui.server import SYSTEM_STATE, LOG_HISTORY
            from datetime import datetime
            
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
                    
                    # 3. Log it
                    log_entry = {"time": time.time(), "msg": f"AI Insight: Sentiment calibrated at {sentiment}."}
                    LOG_HISTORY.append(log_entry)
                    if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
                    
                    logger.info("Intelligence Review Completed.")
                    
        except Exception as e:
            logger.error(f"Intelligence Task Error: {e}")
        
        await asyncio.sleep(3600) # Run every hour

async def main():
    logger.add("logs/engine.log", rotation="10 MB", level="INFO")
    logger.info(f"Initializing {SETTINGS.PROJECT_NAME} v{SETTINGS.VERSION}...")
    logger.success("--- SYSTEM PATCH v5.2.5 ACTIVE (TESTNET-MODERN MODE) ---")
    try:
        # 1. Initialize Telegram Bot (Core UI)
        bot = TelegramBot()
        await bot.start_bot()
        await bot.send_alert(f"🚀 DaNoo v5.2 Engine Online.")
        
        # 2. Start Web UI Server (Background Task)
        ui_server = start_ui_server()
        asyncio.create_task(ui_server.serve())
        logger.info("Web UI Server started on http://0.0.0.0:8000")
        
        # 3. Start Intelligence Task
        asyncio.create_task(run_market_intelligence(bot))
        
        # 4. Initialize Internal Engines
        regime_engine = RegimeEngine()
        
        # 5. Start Routine Orchestration (Scheduler)
        asyncio.create_task(start_scheduler_async())
        
        # 6. Immediate Sync for UI
        from scheduler import cycle_15m
        asyncio.create_task(cycle_15m())
        
        # 7. Initial System Log
        LOG_HISTORY.append({"time": time.time(), "msg": "SYSTEM: DaNoo Command Hub is now LIVE. Monitoring all vectors."})
        
        logger.info("Main loop active. System operational.")
        # Keep the main process alive
        while True:
            await asyncio.sleep(60)
            
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    except Exception as e:
        logger.error(f"Critical System Error: {e}")
    finally:
        logger.info("Clean shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
