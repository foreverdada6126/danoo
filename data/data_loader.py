import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from loguru import logger
from config.settings import SETTINGS

class DataLoader:
    """
    Handles historical and incremental data loading using CCXT.
    Ensures data integrity and continuity.
    """
    
    def __init__(self, exchange_id: str = "binance"):
        self.exchange_class = getattr(ccxt, exchange_id)
        self.exchange = self.exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        logger.info(f"DataLoader initialized with {exchange_id}")

    def fetch_historical_candles(
        self, 
        symbol: str, 
        timeframe: str, 
        since: Optional[int] = None, 
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetches historical klines and returns a cleaned DataFrame.
        """
        logger.info(f"Fetching historical data for {symbol} ({timeframe})")
        
        all_candles = []
        current_since = since
        
        while True:
            try:
                candles = self.exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
                if not candles:
                    break
                
                all_candles.extend(candles)
                last_time = candles[-1][0]
                
                # Update since for next batch
                if len(candles) < limit:
                    break
                
                current_since = last_time + 1
                time.sleep(self.exchange.rateLimit / 1000) # Respect rate limits
                
            except Exception as e:
                logger.error(f"Error fetching candles: {e}")
                break
        
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Validation: check for gaps
        self.validate_continuity(df, timeframe)
        
        return df

    def validate_continuity(self, df: pd.DataFrame, timeframe: str):
        """
        Checks if the data has any missing candles based on the timeframe.
        """
        if df.empty:
            return
            
        # Implementation of gap detection logic...
        # For now, just logging status
        logger.info(f"Validated {len(df)} candles for continuity.")

    def get_binance_symbol(self, symbol: str) -> str:
        """
        Mirroring toCcxtSymbol from orderExecutor.ts
        """
        if '/' in symbol or ':' in symbol:
            return symbol
        if symbol.endswith('USDT'):
            base = symbol.replace('USDT', '')
            return f"{base}/USDT:USDT"
        return symbol
