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

async def main():
    logger.add("logs/engine.log", rotation="10 MB", level="INFO")
    logger.info(f"Initializing {SETTINGS.PROJECT_NAME} v{SETTINGS.VERSION}...")
    
    # 1. Initialize Telegram Bot (Core UI)
    bot = TelegramBot()
    await bot.start_bot()
    await bot.send_alert(f"🚀 System started in *{SETTINGS.MODE}* mode.")
    
    # 2. Start Web UI Server (Background Task)
    ui_server = start_ui_server()
    # Run uvicorn in a way that doesn't block the event loop
    asyncio.create_task(ui_server.serve())
    logger.info("Web UI Server started on http://0.0.0.0:8000")
    
    # 3. Initialize Internal Engines
    regime_engine = RegimeEngine()
    
    # 4. Start Routine Orchestration (Scheduler)
    # The scheduler will run in the background but share the event loop
    try:
        scheduler_task = asyncio.create_task(start_scheduler_async())
        
        logger.info("Main loop active. System operational.")
        # Keep the main process alive
        while True:
            await asyncio.sleep(60)
            
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
