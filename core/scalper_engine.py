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
        from web_ui.state import SYSTEM_STATE, LOG_HISTORY, ACTIVE_TRADES
        
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

                strat_strict = SYSTEM_STATE.get("strat_strict", True)
                strat_loose = SYSTEM_STATE.get("strat_loose", False)
                strat_recon = SYSTEM_STATE.get("strat_recon", False)

                # 4. Entry Logic
                signal = None
                strategy_matched = "UNKNOWN"
                
                if strat_strict and signal is None:
                    if trend_up and prev_k < prev_d and curr_k > curr_d and curr_k < 30:
                        signal = "BUY"
                        strategy_matched = "STRICT_SCALP"
                    elif trend_down and prev_k > prev_d and curr_k < curr_d and curr_k > 70:
                        signal = "SELL"
                        strategy_matched = "STRICT_SCALP"
                        
                if strat_loose and signal is None:
                    if trend_up and prev_k < prev_d and curr_k > curr_d and curr_k < 50:
                        signal = "BUY"
                        strategy_matched = "LOOSE_SCALP"
                    elif trend_down and prev_k > prev_d and curr_k < curr_d and curr_k > 50:
                        signal = "SELL"
                        strategy_matched = "LOOSE_SCALP"
                        
                if strat_recon and signal is None:
                    # Fast momentum proxy via 1m RSI to sync with Intel direction
                    rsi1m = StrategyLibrary.calculate_rsi(close, 14)[-1]
                    if rsi1m > 65 and trend_up:
                        signal = "BUY"
                        strategy_matched = "RECON_SYNC"
                    elif rsi1m < 35 and trend_down:
                        signal = "SELL"
                        strategy_matched = "RECON_SYNC"

                if signal:
                    # One active sub-trade per symbol to prevent double-entry
                    existing = any(t for t in ACTIVE_TRADES if t["symbol"] == symbol and ("SCALP" in t["reason"] or "RECON" in t["reason"]))
                    if not existing:
                        logger.warning(f"[Scalper] SIGNAL: {signal} detected for {symbol} at ${curr_price} via {strategy_matched}")
                        await self.execute_scalp(symbol, signal, curr_price, reason=strategy_matched)
                
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"[Scalper] Scan Error [{symbol}]: {e}")

    async def manage_open_positions(self):
        """Monitors open scalps and executes exits based on TP/SL."""
        from web_ui.state import ACTIVE_TRADES, LOG_HISTORY, SYSTEM_STATE, TRADE_LOG_HISTORY
        
        current_price = SYSTEM_STATE.get("price", 0.0)

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
                amount = db_t.amount
                leverage = trade.get("leverage", 1)
                pnl_pct = ((price - entry_price) / entry_price) if side == "BUY" else ((entry_price - price) / entry_price)
                
                exit_triggered = False
                exit_reason = ""
                if pnl_pct >= 0.005: 
                    exit_triggered = True # 0.5% TP
                    exit_reason = "TAKE_PROFIT"
                elif pnl_pct <= -0.003: 
                    exit_triggered = True # 0.3% SL
                    exit_reason = "STOP_LOSS"
                
                if exit_triggered:
                    close_side = "sell" if side == "BUY" else "buy"
                    close_amount = db_t.amount
                    result = await self.bridge.place_limit_order(trade["symbol"], close_side, close_amount, 0)
                    if result["success"]:
                        db_t.status = "CLOSED"
                        db_t.exit_price = price
                        db_t.exit_time = datetime.utcnow()
                        final_pnl = (price - entry_price) * close_amount * (1 if side == "BUY" else -1)
                        db_t.pnl = final_pnl
                        session.commit()
                        to_close.append(trade)
                        
                        log_msg = f"SCALPER: Finalized {trade['symbol']} scalp at ${price} ({pnl_pct*100:.2f}%) via {exit_reason}"
                        LOG_HISTORY.append({"time": time.time(), "msg": log_msg})
                        
                        # Specialized Trade Log for Intelligence
                        TRADE_LOG_HISTORY.append({
                            "timestamp": time.time(),
                            "action": "EXIT",
                            "symbol": trade["symbol"],
                            "type": side,
                            "price": price,
                            "amount": amount,
                            "leverage": leverage,
                            "pnl": final_pnl,
                            "pnl_pct": pnl_pct * 100,
                            "reason": exit_reason
                        })

                session.close()
            except Exception as e:
                logger.error(f"[Scalper] Position Management Error: {e}")

        for t in to_close:
            if t in ACTIVE_TRADES: ACTIVE_TRADES.remove(t)

    async def execute_scalp(self, symbol: str, side: str, price: float, reason: str = "STRICT_SCALP"):
        """Execute and Persist Scalp Trade using Dynamic Position Sizing."""
        from web_ui.state import ACTIVE_TRADES, LOG_HISTORY, SYSTEM_STATE, TRADE_LOG_HISTORY
        from config.risk_config import RISK_CONFIG
        
        # 1. Base Portfolio Constraint
        equity = SYSTEM_STATE.get("equity", 5000.0)
        if equity <= 0: equity = 5000.0
        
        # 2. Base Risk Allocation (default: 1% of equity to risk losing)
        base_risk_amount = equity * RISK_CONFIG.max_risk_per_trade
        
        # 3. Modify Risk by Strategy Conviction Factor
        if "STRICT" in reason:
            conviction_multiplier = 1.0
        elif "LOOSE" in reason:
            conviction_multiplier = 0.5
        else:
            conviction_multiplier = 0.75
        
        # 4. Apply Regime-Based Weight Adjustment
        regime_weights = SYSTEM_STATE.get("regime_weights", {})
        regime = SYSTEM_STATE.get("regime", "RANGING")
        
        momentum_weight = regime_weights.get("Momentum", 1.0)
        mean_reversion_weight = regime_weights.get("MeanReversion", 1.0)
        
        if regime == "BULL_TREND" and side == "BUY":
            regime_multiplier = momentum_weight
        elif regime == "BEAR_TREND" and side == "SELL":
            regime_multiplier = momentum_weight
        elif regime == "RANGING":
            regime_multiplier = mean_reversion_weight
        elif regime == "HIGH_VOLATILITY":
            regime_multiplier = 0.7
        elif regime == "COMPRESSED":
            regime_multiplier = 1.2
        else:
            regime_multiplier = 1.0
        
        adjusted_max_loss_usdt = base_risk_amount * conviction_multiplier * regime_multiplier
        
        # 4. Calculate Required Leveraged Position Size
        # Formula: Position Size = Max Loss / Stop Loss Percentage
        stop_loss_pct = 0.003  # 0.3% static stop loss used in `manage_open_positions`
        position_size_usdt = adjusted_max_loss_usdt / stop_loss_pct
        
        # 5. Cap Position Size by Maximum Allowed Account Leverage (default 10x)
        leverage = RISK_CONFIG.max_leverage or 10
        absolute_max_position = equity * leverage
        position_size_usdt = min(position_size_usdt, absolute_max_position)
        
        # Enforce Minimum Order Value (Exchange requires > $10 in most cases)
        if position_size_usdt < RISK_CONFIG.min_order_size_usdt:
            logger.warning(f"[Scalper] Capital constraint. Calculated position ${position_size_usdt:.2f} too small.")
            return

        # 6. Calculate Final Asset Amount based on Price
        amount = position_size_usdt / price
        
        # Precision Adjustments based on asset height
        if price > 10000:
            amount = round(amount, 3) # BTC
        elif price > 100:
            amount = round(amount, 2) # ETH, SOL
        else:
            # HBAR, XRP, etc. - ensure integer for low-value assets if they require it
            # Actually, Bybit HBARUSDT usually allows 1-2 decimals, but let's stick to int if 0 was used before
            amount = round(amount, 1) if "HBAR" in symbol else round(amount, 0)
            
        result = self.executor.execute_order(symbol, side.lower(), amount=amount, price=price)
        
        if result["status"] == "FILLED":
            session = DB_SESSION()
            new_trade = Trade(
                symbol=symbol, side=side, amount=amount, entry_price=price,
                entry_time=datetime.utcnow(), status="OPEN", order_id=result["order_id"],
                strategy=reason, leverage=leverage
            )
            session.add(new_trade)
            session.commit()
            
            conviction = "95%" if "STRICT" in reason else ("70%" if "LOOSE" in reason else "85%")
            risk = "LOW" if "STRICT" in reason else ("MED" if "LOOSE" in reason else "HIGH")
            
            ACTIVE_TRADES.append({
                "id": new_trade.id, 
                "time": new_trade.entry_time.timestamp(),
                "symbol": symbol, 
                "type": f"{side} ({reason.split('_')[0]})", 
                "status": "OPEN",
                "pnl": "$0.00", 
                "cost": f"${(amount * price):.2f}",
                "entry_price": price,
                "amount": amount,
                "order_id": new_trade.order_id, 
                "reason": reason,
                "conviction": conviction, 
                "risk": risk, 
                "leverage": leverage
            })
            
            log_msg = f"SCALPER: Entering {side} for {symbol} at ${price} via {reason}"
            LOG_HISTORY.append({"time": time.time(), "msg": log_msg})
            
            # Specialized Trade Log for Intelligence
            TRADE_LOG_HISTORY.append({
                "timestamp": time.time(),
                "action": "ENTRY",
                "symbol": symbol,
                "type": side,
                "price": price,
                "amount": amount,
                "leverage": leverage,
                "amount_usd": position_size_usdt,
                "reason": reason
            })
            
            session.close()
            logger.success(f"[Scalper] Position Live: {symbol} {side} ${price} [{reason}]")
