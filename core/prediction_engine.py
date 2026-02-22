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
        
        return df.fillna(method='bfill')

    async def train_and_predict(self, symbol, ohlcv_data, horizon=4):
        """
        Trains a model on the provided OHLCV data and predicts the next 'horizon' steps.
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
            
            # Incremental training (simply refit for now as RF is fast)
            self.model.fit(X, y)
            self.is_trained = True
            
            # Multi-step prediction (recursive)
            predictions = []
            last_row = df.iloc[-1].copy()
            
            current_close = last_row['close']
            
            for _ in range(horizon):
                X_pred = last_row[features].values.reshape(1, -1)
                next_price = self.model.predict(X_pred)[0]
                predictions.append(float(next_price))
                
                # Update last_row for next recursive step (simplified)
                last_row['close'] = next_price
                # Note: Indicators aren't fully recalculated for speed, just close is bumped
                # In a real system, we'd update all indicators, but this is a proxy for direction
            
            # Confidence based on volatility
            volatility = df['close'].pct_change().std()
            confidence = max(0.6, 1.0 - (volatility * 10))
            
            direction = "BULLISH" if predictions[-1] > current_close else "BEARISH"
            change_pct = ((predictions[-1] - current_close) / current_close) * 100
            
            return {
                "symbol": symbol,
                "current_price": float(current_close),
                "forecast": predictions,
                "direction": direction,
                "change_pct": round(change_pct, 2),
                "confidence": round(confidence * 100, 1),
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Prediction Engine Error: {e}")
            return None
