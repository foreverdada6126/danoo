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
        """Monitor every asset in the watchlist (1m heartbeat)."""
        from web_ui.server import SYSTEM_STATE, LOG_HISTORY, ACTIVE_TRADES
        
        # Don't overlap scans
        if time.time() - self.last_scan_time < 50:
            return
        self.last_scan_time = time.time()

        logger.info(f"[Scalper] Watchlist Heartbeat: Scanning {len(SETTINGS.WATCHLIST)} assets...")
        
        # 1. Manage Open Scalps First
        await self.manage_open_positions()

        # 2. Iterate through Watchlist
        for symbol in SETTINGS.WATCHLIST:
            try:
                client = await self.bridge._get_client()
                ohlcv = await client.fetch_ohlcv(symbol, "1m", limit=100)
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
                if trend_up and prev_k < prev_d and curr_k > curr_d and curr_k < 30:
                    signal = "BUY"
                if trend_down and prev_k > prev_d and curr_k < curr_d and curr_k > 70:
                    signal = "SELL"

                if signal:
                    # One active scalp per symbol
                    existing = any(t for t in ACTIVE_TRADES if t["symbol"] == symbol and "SCALP" in t["reason"])
                    if not existing:
                        logger.warning(f"[Scalper] SIGNAL: {signal} detected for {symbol} at ${curr_price}")
                        await self.execute_scalp(symbol, signal, curr_price)
                
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"[Scalper] Scan Error [{symbol}]: {e}")

    async def manage_open_positions(self):
        """Monitors open scalps and executes exits based on TP/SL."""
        from web_ui.server import ACTIVE_TRADES, LOG_HISTORY, SYSTEM_STATE
        
        current_price = SYSTEM_STATE.get("price", 0.0)
        # Note: In multi-asset mode, we'd ideally fetch current price per symbol.
        # For simplicity in this pulse, we fetch fresh price during exit check if needed.

        to_close = []
        for trade in ACTIVE_TRADES:
            if "SCALP" not in trade["reason"]: continue
            
            try:
                # Fresh price for the specific symbol
                client = await self.bridge._get_client()
                ticker = await client.fetch_ticker(trade["symbol"])
                price = ticker['last']

                session = DB_SESSION()
                db_t = session.query(Trade).filter(Trade.order_id == trade["order_id"]).first()
                if not db_t: 
                    session.close()
                    continue
                
                entry_price = db_t.entry_price
                side = db_t.side
                pnl_pct = ((price - entry_price) / entry_price) if side == "BUY" else ((entry_price - price) / entry_price)
                
                exit_triggered = False
                if pnl_pct >= 0.005: exit_triggered = True # 0.5% TP
                elif pnl_pct <= -0.003: exit_triggered = True # 0.3% SL
                
                if exit_triggered:
                    close_side = "sell" if side == "BUY" else "buy"
                    result = await self.bridge.place_limit_order(trade["symbol"], close_side, 0.001, 0)
                    if result["success"]:
                        db_t.status = "CLOSED"
                        db_t.exit_price = price
                        db_t.exit_time = datetime.utcnow()
                        db_t.pnl = (price - entry_price) * 0.001 * (1 if side == "BUY" else -1)
                        session.commit()
                        to_close.append(trade)
                        LOG_HISTORY.append({"time": time.time(), "msg": f"SCALPER: Finalized {trade['symbol']} scalp at ${price} ({pnl_pct*100:.2f}%)"})

                session.close()
            except Exception as e:
                logger.error(f"[Scalper] Position Management Error: {e}")

        for t in to_close:
            if t in ACTIVE_TRADES: ACTIVE_TRADES.remove(t)

    async def execute_scalp(self, symbol: str, side: str, price: float):
        """Execute and Persist Scalp Trade."""
        from web_ui.server import ACTIVE_TRADES, LOG_HISTORY
        
        amount = 0.001 
        result = self.executor.execute_order(symbol, side.lower(), amount=amount, price=price)
        
        if result["status"] == "FILLED":
            session = DB_SESSION()
            new_trade = Trade(
                symbol=symbol, side=side, amount=amount, entry_price=price,
                entry_time=datetime.utcnow(), status="OPEN", order_id=result["order_id"],
                strategy="SCALP-EMA-STOCH"
            )
            session.add(new_trade)
            session.commit()
            
            ACTIVE_TRADES.append({
                "id": new_trade.id, "time": new_trade.entry_time.timestamp(),
                "symbol": symbol, "type": f"{side} (SCALP)", "status": "OPEN",
                "pnl": "$0.00", "order_id": new_trade.order_id, "reason": "SCALP-EMA-STOCH"
            })
            LOG_HISTORY.append({"time": time.time(), "msg": f"SCALPER: Entering {side} scalp for {symbol} at ${price}"})
            session.close()
            logger.success(f"[Scalper] Position Live: {symbol} {side} ${price}")
