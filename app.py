"""
Adaptive Strategy Intelligence Engine v5.2 - Main Orchestrator
"""
import asyncio
import sys
from loguru import logger
from config.settings import SETTINGS
from core.regime_engine import RegimeEngine
from telegram_bot.bot import TelegramBot
from scheduler import start_scheduler_async
from web_ui.server import start_ui_server

import httpx

async def run_market_intelligence(bot):
    """Periodically call intel-service for AI-driven sentiment analysis."""
    while True:
        try:
            from web_ui.server import SYSTEM_STATE, LOG_HISTORY
            from datetime import datetime
            
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
                    # 2. Update Dashboard State
                    SYSTEM_STATE["ai_insight"] = data["analysis"][:200] + "..."
                    SYSTEM_STATE["sentiment_score"] = data["sentiment_estimate"]
                    
                    # 3. Log it
                    log_entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": f"AI Insight: Market is {data['sentiment_estimate']} sentiment."}
                    LOG_HISTORY.append(log_entry)
                    if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
                    
                    logger.info("Intelligence Review Completed.")
                    
        except Exception as e:
            logger.error(f"Intelligence Task Error: {e}")
        
        await asyncio.sleep(3600) # Run every hour

async def main():
    logger.add("logs/engine.log", rotation="10 MB", level="INFO")
    logger.info(f"Initializing {SETTINGS.PROJECT_NAME} v{SETTINGS.VERSION}...")
    
    # ... (Bot and UI init) ...
    bot = TelegramBot()
    await bot.start_bot()
    
    ui_server = start_ui_server()
    asyncio.create_task(ui_server.serve())
    
    # 3. Start Intelligence Task
    asyncio.create_task(run_market_intelligence(bot))
    
    # 4. Initialize Internal Engines
    # ...
            
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    except Exception as e:
        logger.error(f"Critical System Error: {e}")
        await bot.send_alert(f"❌ CRITICAL ERROR: {e}")
    finally:
        logger.info("Clean shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
