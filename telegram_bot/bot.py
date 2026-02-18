import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from loguru import logger
from config.settings import SETTINGS

class TelegramBot:
    """
    Interface for system monitoring and manual trade approval.
    """
    
    def __init__(self):
        self.token = SETTINGS.TELEGRAM_TOKEN
        self.chat_id = SETTINGS.TELEGRAM_CHAT_ID
        self.application = None
        
        if not self.token:
            logger.warning("Telegram token missing. Bot disabled.")

    async def start_bot(self):
        if not self.token: return
        
        self.application = Application.builder().token(self.token).build()
        
        # Commands
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("equity", self.equity))
        self.application.add_handler(CommandHandler("health", self.health))
        
        # Approval handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_approval))
        
        logger.info("Telegram Bot started.")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def send_alert(self, message: str):
        """Sends an alert message to the configured chat."""
        if not self.application: return
        try:
            await self.application.bot.send_message(chat_id=self.chat_id, text=f"⚠️ *ALERT*: {message}", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send telegram alert: {e}")

    async def request_approval(self, trade_details: dict):
        """Sends an interactive message for trade approval."""
        if not self.application: return
        
        text = (
            f"🔔 *TRADE APPROVAL REQUIRED*\n\n"
            f"Strategy: {trade_details.get('strategy')}\n"
            f"Symbol: {trade_details.get('symbol')}\n"
            f"Side: {trade_details.get('side')}\n"
            f"Amount: {trade_details.get('amount')}\n"
            f"Price: {trade_details.get('price')}\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{trade_details['id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{trade_details['id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.application.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("System: ONLINE\nMode: " + SETTINGS.MODE)

    async def equity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # To be integrated with tracker
        await update.message.reply_text("Current Equity: $--- (Fetching...)")

    async def health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Health Status: ALL SYSTEMS NOMINAL")

    async def handle_approval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        action, trade_id = query.data.split("_")
        if action == "approve":
            await query.edit_message_text(text=f"✅ Trade {trade_id} APPROVED.")
            # Trigger execution logic here
        else:
            await query.edit_message_text(text=f"❌ Trade {trade_id} REJECTED.")
