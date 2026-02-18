import numpy as np
import pandas as pd
from typing import Dict, Any, List
from core.strategy_library import StrategyLibrary

class RegimeEngine:
    """
    Analyzes market regimes based on trend, volatility, and compression.
    Aligns with backtester.ts and adaptive strategy intelligence.
    """
    
    REGIMES = ["BULL_TREND", "BEAR_TREND", "RANGING", "COMPRESSED", "HIGH_VOLATILITY"]

    def analyze(self, df: pd.DataFrame) -> str:
        """
        Classifies the latest market regime.
        """
        if len(df) < 50:
            return "UNKNOWN"
            
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # 1. Trend Analysis (EMA 20 vs 50)
        ema20 = StrategyLibrary.calculate_ema(close, 20)
        ema50 = StrategyLibrary.calculate_ema(close, 50)
        
        latest_ema20 = ema20[-1]
        latest_ema50 = ema50[-1]
        
        # 2. Volatility / Compression (BB Width Percentile)
        bb = StrategyLibrary.calculate_bollinger_bands(close, 20, 2)
        bb_width = bb['width']
        
        # Calculate percentile rank of current width (mirroring legacy logic)
        current_width = bb_width[-1]
        width_history = bb_width[-100:]
        width_history = width_history[~np.isnan(width_history)]
        
        width_percentile = (np.sum(width_history < current_width) / len(width_history)) * 100
        
        # 3. High Volatility Check
        atr = StrategyLibrary.calculate_atr(high, low, close, 14)
        atr_rel = (atr[-1] / close[-1]) * 100
        
        # Classification Logic
        if width_percentile < 15:
            return "COMPRESSED"
            
        if atr_rel > 3.0: # Threshold for high volatility regime
            return "HIGH_VOLATILITY"
            
        if latest_ema20 > latest_ema50 * 1.002: # Slight buffer for trend
            return "BULL_TREND"
        elif latest_ema20 < latest_ema50 * 0.998:
            return "BEAR_TREND"
        else:
            return "RANGING"

    def get_regime_weights(self, regime: str) -> Dict[str, float]:
        """
        AI Meta Layer suggestion: Adjust strategy weights based on regime.
        """
        weights = {
            "BULL_TREND": {"VolatilityExpansion": 1.2, "MeanReversion": 0.5, "Momentum": 1.5},
            "BEAR_TREND": {"VolatilityExpansion": 1.2, "MeanReversion": 0.5, "Momentum": 1.5},
            "RANGING": {"VolatilityExpansion": 0.5, "MeanReversion": 1.5, "Momentum": 0.3},
            "COMPRESSED": {"VolatilityExpansion": 2.0, "MeanReversion": 0.5, "Momentum": 1.0},
            "HIGH_VOLATILITY": {"VolatilityExpansion": 0.8, "MeanReversion": 0.8, "Momentum": 0.8}
        }
        return weights.get(regime, {"default": 1.0})
