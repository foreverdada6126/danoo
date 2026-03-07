import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from loguru import logger
import time

class PredictionEngine:
    """
    DaNoo Intelligence: ML-based Price Discovery & Forecasting.
    Uses Random Forest Regressor calibrated with Technical Indicators.
    """
    def __init__(self, n_estimators=100):
        self.model = RandomForestRegressor(n_estimators=n_estimators, random_state=42)
        self.is_trained = False
        self.last_train_time = 0
        self.symbols_trained = {}

    def _calculate_indicators(self, df):
        """Standard institutional feature engineering."""
        # Moving Averages
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
        
        # Volatility
        df['std_20'] = df['close'].rolling(window=20).std()
        df['bb_up'] = df['sma_20'] + (df['std_20'] * 2)
        df['bb_down'] = df['sma_20'] - (df['std_20'] * 2)
        
        # Momentum
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # Stochastic
        low_min = df['low'].rolling(window=14).min()
        high_max = df['high'].rolling(window=14).max()
        df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
        
        return df.ffill().bfill()

    async def train_and_predict(self, symbol, ohlcv_data, horizon=4, liquidity_data=None):
        """
        Trains a model and predicts next steps, now factoring in institutional liquidity walls.
        """
        try:
            df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = self._calculate_indicators(df)
            
            # Feature columns
            features = ['close', 'sma_20', 'sma_50', 'ema_15', 'rsi', 'macd', 'stoch_k', 'stoch_d', 'bb_up', 'bb_down']
            
            # Target: Next price
            df['target'] = df['close'].shift(-1)
            
            train_df = df.dropna()
            if len(train_df) < 50:
                return None

            X = train_df[features].values
            y = train_df['target'].values
            
            self.model.fit(X, y)
            self.is_trained = True
            
            # Recursive Forecast
            predictions = []
            last_row = df.iloc[-1].copy()
            current_close = last_row['close']
            
            for _ in range(horizon):
                X_pred = last_row[features].values.reshape(1, -1)
                next_price = self.model.predict(X_pred)[0]
                predictions.append(float(next_price))
                last_row['close'] = next_price
            
            # ─── INSTITUTIONAL LIQUIDITY ADJUSTMENT ───
            final_forecast = predictions[-1]
            direction = "BULLISH" if final_forecast > current_close else "BEARISH"
            change_pct = ((final_forecast - current_close) / current_close) * 100
            confidence_mod = 0
            
            if liquidity_data:
                res = liquidity_data.get("resistance", 999999)
                sup = liquidity_data.get("support", 0)
                imbalance = liquidity_data.get("imbalance", 0) # -1.0 to 1.0
                
                # 1. Price Capping (The "Expert" Guardrail)
                if direction == "BULLISH" and final_forecast > res:
                    # ML is bullish but there's a WHALE WALL in the way
                    final_forecast = res * 0.9998 # Adjust to just below the wall
                    direction = "BULL_REJECTED" # Flag the institutional barrier
                    confidence_mod -= 20
                    logger.warning(f"ML BULLISH but LIQUIDITY REJECTED for {symbol}. Capping at {res}")
                
                elif direction == "BEARISH" and final_forecast < sup:
                    final_forecast = sup * 1.0002
                    direction = "BEAR_SUPPORTED"
                    confidence_mod -= 15
                
                # 2. Imbalance Influence
                # If ML and Imbalance agree, boost confidence
                if (direction == "BULLISH" and imbalance > 0.2) or (direction == "BEARISH" and imbalance < -0.2):
                    confidence_mod += 15
            
            # Confidence based on volatility
            volatility = df['close'].pct_change().std()
            base_confidence = max(0.6, 1.0 - (volatility * 10))
            final_confidence = min(99.0, max(40.0, (base_confidence * 100) + confidence_mod))
            
            return {
                "symbol": symbol,
                "current_price": float(current_close),
                "forecast": predictions,
                "adjusted_target": float(final_forecast),
                "direction": direction,
                "change_pct": round(((final_forecast - current_close) / current_close) * 100, 3),
                "confidence": round(final_confidence, 1),
                "timestamp": time.time(),
                "institutional_backed": True if (liquidity_data and abs(confidence_mod) > 0) else False
            }
            
        except Exception as e:
            logger.error(f"Prediction Engine Error: {e}")
            return None
