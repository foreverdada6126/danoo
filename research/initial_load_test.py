import pandas as pd
import numpy as np
import time
from loguru import logger
from data.data_loader import DataLoader
from core.regime_engine import RegimeEngine
from core.strategy_library import StrategyLibrary

def run_initial_load_and_test():
    """
    1. Fetches rich historical BTC data across various regimes.
    2. Runs analysis to verify 'The Brain' is working.
    3. Populates initial state for the UI.
    """
    logger.info("Starting initial Data Pull & Brain Testing for BTC...")
    loader = DataLoader(exchange_id="binance")
    regime_engine = RegimeEngine()
    
    # 1. Fetch 1000 candles of 1h data for a broad view
    try:
        df = loader.fetch_historical_candles("BTC/USDT", "1h", limit=1000)
        if df.empty:
            logger.error("Failed to fetch data. Check internet/API.")
            return
        
        # 2. Analyze Regime
        current_regime = regime_engine.analyze(df)
        logger.info(f"Analysis Complete. Current Market Regime: {current_regime}")
        
        # 3. Calculate Meta Signals (Indicators)
        close = df['close'].values
        ema20 = StrategyLibrary.calculate_ema(close, 20)
        ema50 = StrategyLibrary.calculate_ema(close, 50)
        rsi = StrategyLibrary.calculate_rsi(close, 14)
        
        trend = "BULLISH" if ema20[-1] > ema50[-1] else "BEARISH"
        
        # 4. Save to a temporary state file for UI to pick up
        metadata = {
            "symbol": "BTCUSDT",
            "regime": current_regime,
            "trend": trend,
            "rsi": round(rsi[-1], 2),
            "last_price": close[-1],
            "data_points": len(df)
        }
        
        # (Writing to data/processed for persistence)
        df.to_csv("data/processed/btc_initial_data.csv")
        logger.info("Initial dataset saved to data/processed/btc_initial_data.csv")
        
        return metadata

    except Exception as e:
        logger.error(f"Error in initial load: {e}")
        return None

if __name__ == "__main__":
    run_initial_load_and_test()
