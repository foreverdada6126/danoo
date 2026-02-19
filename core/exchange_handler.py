import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import asyncio
import time
from loguru import logger
from config.settings import SETTINGS

class ExchangeHandler:
    def __init__(self):
        self.exchange_id = SETTINGS.EXCHANGE_ID
        self.api_key = SETTINGS.BINANCE_API_KEY
        self.secret = SETTINGS.BINANCE_SECRET
        self.use_sandbox = SETTINGS.USE_SANDBOX
        
        # Initialize Async CCXT exchange
        exchange_class = getattr(ccxt, self.exchange_id)
        self.client = exchange_class({
            'apiKey': self.api_key,
            'secret': self.secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} 
        })
        
        if self.use_sandbox:
            self.client.set_sandbox_mode(True)
            logger.info(f"Exchange Bridge: {self.exchange_id.upper()} initialized in SANDBOX mode.")
        else:
            logger.warning(f"Exchange Bridge: {self.exchange_id.upper()} initialized in PRODUCTION mode.")

    async def fetch_balance(self):
        """Aggressively fetches the USDT balance from the futures wallet."""
        if not self.api_key or not self.secret:
            return 5000.0 if self.use_sandbox else 0.0
            
        try:
            balance = await self.client.fetch_balance()
            
            # Discovery Path 1: Standard Total
            usdt_bal = balance.get('total', {}).get('USDT', 0.0)
            
            # Discovery Path 2: Individual Entry
            if usdt_bal == 0:
                usdt_bal = balance.get('USDT', {}).get('total', 0.0)
            
            # Discovery Path 3: Info Entry (Binance Raw)
            if usdt_bal == 0 and 'info' in balance:
                assets = balance['info'].get('assets', [])
                for asset in assets:
                    if asset.get('asset') == 'USDT':
                        usdt_bal = float(asset.get('walletBalance', 0.0))
                        break
            
            logger.info(f"Exchange Bridge: Balance Discovery complete. USDT: {usdt_bal}")
            return float(usdt_bal)
        except Exception as e:
            logger.error(f"Balance Fetch Error: {str(e)}")
            return None

    async def fetch_market_data(self, symbol=None, timeframe=None):
        """Fetches RSI and Funding Rate for the dashboard."""
        symbol = symbol or SETTINGS.DEFAULT_SYMBOL
        timeframe = timeframe or SETTINGS.DEFAULT_TIMEFRAME
        
        try:
            # 1. Fetch OHLCV for RSI
            ohlcv = self.client.fetch_ohlcv(symbol, timeframe, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Simple RSI Calculation
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # 2. Fetch Funding Rate
            funding = self.client.fetch_funding_rate(symbol)
            funding_rate = funding.get('fundingRate', 0.0) * 100 # Convert to percentage
            
            price = df['close'].iloc[-1]
            
            return {
                "price": price,
                "rsi": round(float(current_rsi), 2) if not np.isnan(current_rsi) else 50.0,
                "funding_rate": round(funding_rate, 4),
                "timestamp": df['timestamp'].iloc[-1]
            }
        except Exception as e:
            logger.error(f"Exchange Bridge Error: {str(e)}")
            return None

    async def place_limit_order(self, symbol, side, amount, price):
        """Places a real (sandbox) limit order with paper fallback."""
        if not self.api_key or not self.secret:
            if self.use_sandbox:
                logger.info("Exchange Bridge: No API keys found. Simulating Paper Execution...")
                await asyncio.sleep(0.5) 
                return {
                    "success": True,
                    "order": {
                        'id': f'sim-{int(time.time())}',
                        'info': {'status': 'FILLED', 'type': 'PAPER_SIM'},
                        'status': 'closed',
                        'symbol': symbol,
                        'side': side,
                        'price': price,
                        'amount': amount
                    }
                }
            else:
                return {"success": False, "error": "Production Keys Missing"}

        try:
            # 1. Fetch latest ticker if price is missing or zero
            if not price or price < 0.1:
                logger.info(f"Exchange Bridge: Price missing or invalid ({price}). Fetching current ticker...")
                ticker = await self.client.fetch_ticker(symbol)
                price = ticker['last']

            # 2. Format price for the exchange precision
            # CCXT provides helper for this
            formatted_price = self.client.price_to_precision(symbol, price)
            
            order = await self.client.create_limit_order(symbol, side, amount, formatted_price)
            logger.success(f"EXCHANGE SUCCESS: {order['id']}")
            return {"success": True, "order": order}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"EXCHANGE REJECTION: {error_msg}")
            # Identify common errors
            if "AuthenticationError" in error_msg: error_msg = "Invalid API Keys / Secret"
            elif "PermissionDenied" in error_msg: error_msg = "API Keys do not have Futures enabled"
            elif "InsufficientFunds" in error_msg: error_msg = "Insufficient Margin in Futures Wallet"
            
            return {"success": False, "error": error_msg}
