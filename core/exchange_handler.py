import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import asyncio
import time
from loguru import logger
from config.settings import SETTINGS

# --- Persistent Global Clients ---
_CLIENT_INSTANCE = None
_PUBLIC_CLIENT = None

async def get_exchange_client(force_public=False):
    global _CLIENT_INSTANCE, _PUBLIC_CLIENT
    
    if force_public:
        if _PUBLIC_CLIENT is None:
            exchange_id = SETTINGS.EXCHANGE_ID
            exchange_class = getattr(ccxt, exchange_id)
            # Public mainnet client for real data display
            _PUBLIC_CLIENT = exchange_class({
                'enableRateLimit': True,
                'options': {'defaultType': 'swap' if exchange_id == "bybit" else 'future'}
            })
            logger.info(f"Exchange Bridge: Public Mainnet Client created for {exchange_id.upper()}.")
        return _PUBLIC_CLIENT

    if _CLIENT_INSTANCE is None:
        exchange_id = SETTINGS.EXCHANGE_ID
        if exchange_id == "bybit":
            api_key = SETTINGS.BYBIT_API_KEY
            secret = SETTINGS.BYBIT_SECRET
            _default_type = 'swap'
        else:
            api_key = SETTINGS.BINANCE_API_KEY
            secret = SETTINGS.BINANCE_SECRET
            _default_type = 'future'

        exchange_class = getattr(ccxt, exchange_id)
        config = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {'defaultType': _default_type} 
        }
        client = exchange_class(config)

        if SETTINGS.USE_SANDBOX:
            if exchange_id == "binance":
                client.urls.update({
                    'api': {
                        'public': 'https://testnet.binancefuture.com/fapi/v1',
                        'private': 'https://testnet.binancefuture.com/fapi/v1',
                    },
                    'fapiPublic': 'https://testnet.binancefuture.com/fapi/v1',
                    'fapiPrivate': 'https://testnet.binancefuture.com/fapi/v1',
                })
            else:
                client.set_sandbox_mode(True)
            logger.info(f"Exchange Bridge: Persistent Client created for {exchange_id.upper()} TESTNET.")
        else:
            logger.info(f"Exchange Bridge: Persistent Client created for {exchange_id.upper()} PRODUCTION.")
            
        _CLIENT_INSTANCE = client
    return _CLIENT_INSTANCE

class ExchangeHandler:
    def __init__(self):
        self.api_key = SETTINGS.BYBIT_API_KEY if SETTINGS.EXCHANGE_ID == "bybit" else SETTINGS.BINANCE_API_KEY
        self.use_sandbox = SETTINGS.USE_SANDBOX

    async def _get_client(self, force_public=False):
        return await get_exchange_client(force_public)

    async def fetch_balance(self):
        if not self.api_key:
            return 5000.0 if self.use_sandbox else 0.0
        try:
            client = await self._get_client()
            await client.load_markets()
            balance = await client.fetch_balance()
            usdt_bal = balance.get('total', {}).get('USDT', 0.0)
            if usdt_bal == 0:
                usdt_bal = balance.get('USDT', {}).get('total', 0.0)
            logger.info(f"Exchange Bridge: Connection SUCCESS. Detected Balance: ${usdt_bal}")
            return float(usdt_bal)
        except Exception as e:
            logger.error(f"Exchange Bridge: Balance Failure: {str(e)}")
            return None

    async def fetch_market_data(self, symbol=None, timeframe=None):
        symbol = symbol or SETTINGS.DEFAULT_SYMBOL
        timeframe = timeframe or SETTINGS.DEFAULT_TIMEFRAME
        try:
            # Always use public mainnet for stats display
            client = await self._get_client(force_public=True)
            await client.load_markets()
            ohlcv = await client.fetch_ohlcv(symbol, timeframe, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            funding = await client.fetch_funding_rate(symbol)
            funding_rate = funding.get('fundingRate', 0.0) * 100 
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
        if not self.api_key:
            return {"success": True, "order": {"id": f"sim-{int(time.time())}", "status": "closed", "price": price, "amount": amount}}
        try:
            client = await self._get_client() # Uses Sandbox if SETTINGS.USE_SANDBOX
            await client.load_markets()
            formatted_amount = float(client.amount_to_precision(symbol, amount))
            order = await client.create_market_order(symbol, side, formatted_amount)
            return {"success": True, "order": order}
        except Exception as e:
            logger.error(f"EXCHANGE REJECTION: {str(e)}")
            return {"success": False, "error": str(e)}

    async def close(self):
        pass
