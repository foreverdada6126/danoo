import asyncio
import numpy as np
import pandas as pd
from loguru import logger
from core.exchange_handler import ExchangeHandler
from core.strategy_library import StrategyLibrary
from core.execution_engine import ExecutionEngine
from config.settings import SETTINGS
from database.models import DB_SESSION, Trade
from datetime import datetime
import time

class ScalperEngine:
    """
    Hybrid Scalper Engine (Based on Proven LTF Strategies).
    Trend: EMA 9 / EMA 21
    Momentum: Stochastic (9,3,3)
    Timeframe: 1m
    """
    def __init__(self):
        self.bridge = ExchangeHandler()
        self.executor = ExecutionEngine(mode=SETTINGS.MODE)
        self.last_scan_time = 0

    async def scan_market(self):
        """Perform market scan and also manage open positions."""
        from web_ui.server import SYSTEM_STATE, LOG_HISTORY, ACTIVE_TRADES
        
        # Don't overlap scans
        if time.time() - self.last_scan_time < 50:
            return
        self.last_scan_time = time.time()

        logger.info("[Scalper] Heartbeat: Scanning for opportunities & managing open positions...")
        
        # 1. Manage Open Scalps First
        await self.manage_open_positions()

        try:
            # 2. Fetch 1m Candle Data
            client = await self.bridge._get_client()
            ohlcv = await client.fetch_ohlcv(SETTINGS.DEFAULT_SYMBOL, "1m", limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values

            # 3. Calculate Indicators
            ema9 = StrategyLibrary.calculate_ema(close, 9)
            ema21 = StrategyLibrary.calculate_ema(close, 21)
            stoch = StrategyLibrary.calculate_stochastic(high, low, close, 9, 3, 3)
            
            curr_price = close[-1]
            curr_k = stoch['k'][-1]
            curr_d = stoch['d'][-1]
            prev_k = stoch['k'][-2]
            prev_d = stoch['d'][-2]
            
            trend_up = ema9[-1] > ema21[-1]
            trend_down = ema9[-1] < ema21[-1]

            # 4. Entry Logic
            signal = None
            
            # LONG: Trend Up + Stoch Cross Up in Oversold (<30)
            if trend_up and prev_k < prev_d and curr_k > curr_d and curr_k < 30:
                signal = "BUY"
            
            # SHORT: Trend Down + Stoch Cross Down in Overbought (>70)
            if trend_down and prev_k > prev_d and curr_k < curr_d and curr_k > 70:
                signal = "SELL"

            if signal:
                # Only one active scalp at a time per symbol for risk control
                existing = any(t for t in ACTIVE_TRADES if t["symbol"] == SETTINGS.DEFAULT_SYMBOL and "SCALP" in t["reason"])
                if not existing:
                    logger.warning(f"[Scalper] SIGNAL DETECTED: {signal} at ${curr_price}")
                    await self.execute_scalp(signal, curr_price)
                else:
                    logger.debug("[Scalper] Position already exists. Skipping entry.")

        except Exception as e:
            logger.error(f"[Scalper] Scan Error: {e}")

    async def manage_open_positions(self):
        """Monitors open scalps and executes exits based on TP/SL."""
        from web_ui.server import ACTIVE_TRADES, LOG_HISTORY, SYSTEM_STATE
        
        current_price = SYSTEM_STATE.get("price", 0.0)
        if current_price == 0: return

        # Fixed Scalp Targets (aggressive for 1m timeframe)
        TP_PCT = 0.005 # 0.5%
        SL_PCT = 0.003 # 0.3%

        to_close = []
        for trade in ACTIVE_TRADES:
            if "SCALP" not in trade["reason"]: continue
            
            # Fetch full trade data from DB to get entry price accurately
            try:
                session = DB_SESSION()
                db_t = session.query(Trade).filter(Trade.order_id == trade["order_id"]).first()
                if not db_t: 
                    session.close()
                    continue
                
                entry_price = db_t.entry_price
                side = db_t.side # BUY/SELL
                
                # Calculate PnL %
                if side == "BUY":
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                
                # Check Exit Conditions
                exit_triggered = False
                exit_reason = ""
                
                if pnl_pct >= TP_PCT:
                    exit_triggered = True
                    exit_reason = "TAKE PROFIT (SCALP)"
                elif pnl_pct <= -SL_PCT:
                    exit_triggered = True
                    exit_reason = "STOP LOSS (SCALP)"
                
                if exit_triggered:
                    logger.success(f"[Scalper] EXIT TRIGGERED: {exit_reason} for {trade['order_id']} at ${current_price} ({pnl_pct*100:.2f}%)")
                    
                    # Execute Close
                    close_side = "sell" if side == "BUY" else "buy"
                    result = await self.bridge.place_limit_order(trade["symbol"], close_side, 0.001, 0) # Market close
                    
                    if result["success"]:
                        db_t.status = "CLOSED"
                        db_t.exit_price = current_price
                        db_t.exit_time = datetime.utcnow()
                        db_t.pnl = (current_price - entry_price) * 0.001 * (1 if side == "BUY" else -1)
                        session.commit()
                        to_close.append(trade)
                        LOG_HISTORY.append({"time": time.time(), "msg": f"SCALPER: Closed position {trade['order_id']} via {exit_reason}"})

                session.close()
            except Exception as e:
                logger.error(f"[Scalper] Management Error: {e}")

        # Clean up memory list
        for t in to_close:
            if t in ACTIVE_TRADES:
                ACTIVE_TRADES.remove(t)

    async def execute_scalp(self, side: str, price: float):
        """Execute and Persist Scalp Trade."""
        from web_ui.server import ACTIVE_TRADES, LOG_HISTORY
        
        symbol = SETTINGS.DEFAULT_SYMBOL
        # Scalping uses small, precise amounts
        amount = 0.001 
        
        result = self.executor.execute_order(symbol, side.lower(), amount=amount, price=price)
        
        if result["status"] == "FILLED":
            # Persist to DB
            session = DB_SESSION()
            new_trade = Trade(
                symbol=symbol,
                side=side,
                amount=amount,
                entry_price=price,
                entry_time=datetime.utcnow(),
                status="OPEN",
                order_id=result["order_id"],
                strategy="SCALP-EMA-STOCH"
            )
            session.add(new_trade)
            session.commit()
            
            # Add to UI Memory
            trade_data = {
                "id": new_trade.id,
                "time": new_trade.entry_time.timestamp(),
                "symbol": symbol,
                "type": f"{side} (SCALP)",
                "status": "OPEN",
                "pnl": "$0.00",
                "order_id": new_trade.order_id,
                "reason": "SCALP-EMA-STOCH"
            }
            ACTIVE_TRADES.append(trade_data)
            LOG_HISTORY.append({"time": time.time(), "msg": f"SCALPER: Executed {side} scalp at ${price}"})
            
            session.close()
            logger.success(f"[Scalper] Scalp POSITION PERSISTED: {side} ${price}")
