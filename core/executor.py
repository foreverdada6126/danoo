from loguru import logger
from typing import Dict, Any
import time
from core.execution_engine import ExecutionEngine

class StrategicBridge:
    """
    The Strategic Bridge: Combines Market Regime (Technical) with AI Sentiment (Executive).
    Triggers higher-level trades based on regime/sentiment alignment.
    """
    
    def __init__(self):
        self.min_sentiment_threshold = 0.25
        self.max_volatility_limit = 4.0
        self.executor = ExecutionEngine(mode="paper")
        
    def check_trade_readiness(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified check: Should we execute a higher-level strategic trade?
        """
        regime = state.get("regime", "UNKNOWN")
        sentiment = state.get("sentiment_score", 0.0)
        
        logger.info(f"Strategic Scan: Regime={regime} | Sentiment={sentiment}")
        
        # 1. Check AI Sentiment (The Master Guard)
        if regime == "BULL_TREND" and sentiment < self.min_sentiment_threshold:
            return {
                "decision": "BLOCK",
                "reason": f"AI Divergence: Technical Bullish but Sentiment too low ({sentiment})."
            }
            
        if regime == "BEAR_TREND" and sentiment > -self.min_sentiment_threshold:
            return {
                "decision": "BLOCK",
                "reason": f"AI Divergence: Technical Bearish but Sentiment too high ({sentiment})."
            }

        # 2. Regime-Based Guard
        if regime == "HIGH_VOLATILITY":
            return {
                "decision": "BLOCK",
                "reason": "Volatility Spike: Market outside safe strategic execution parameters."
            }

        if regime == "COMPRESSED":
            return {
                "decision": "WATCH",
                "reason": "Market Coiling: Awaiting breakout before strategic entry."
            }

        # 3. Final Readiness
        if (regime == "BULL_TREND" and sentiment >= self.min_sentiment_threshold) or \
           (regime == "BEAR_TREND" and sentiment <= -self.min_sentiment_threshold):
            return {
                "decision": "READY",
                "reason": "Strategic Alignment: Technical Regime and AI Sentiment are synchronized."
            }

        return {
            "decision": "WAIT",
            "reason": "Neutral market conditions: No strategic edge detected."
        }

    async def execute_strategic_trade(self, state: Dict[str, Any], decision_data: Dict[str, Any]):
        """
        Actually executes a trade based on strategic alignment.
        """
        if decision_data["decision"] != "READY":
             return False

        symbol = state.get("symbol", "BTCUSDT")
        regime = state.get("regime", "UNKNOWN")
        side = "buy" if regime == "BULL_TREND" else "sell"
        price = state.get("price", 0.0)
        
        # Logic to calculate amount based on balance
        from config.settings import SETTINGS
        total_equity = state.get("equity", 1000.0 * len(SETTINGS.WATCHLIST))
        equity = total_equity / len(SETTINGS.WATCHLIST) if len(SETTINGS.WATCHLIST) > 0 else 1000.0
        
        amount_usd = equity * 0.10 # Use 10% of equity slice for strategic trades
        if price <= 0: return False
        
        amount = amount_usd / price
        
        # Round based on asset
        amount = round(amount, 3) if "BTC" in symbol or "ETH" in symbol else round(amount, 0)

        logger.info(f"STRATEGIC EXECUTION: Starting {side.upper()} order for {symbol}...")
        
        # Ensure mode matches system state
        self.executor.mode = state.get("mode", "PAPER").lower()
        
        result = await self.executor.execute_order(symbol, side, amount, price)
        
        if result["status"] == "FILLED":
            from database.models import DB_SESSION, Trade
            from datetime import datetime
            from web_ui.state import ACTIVE_TRADES, LOG_HISTORY
            
            session = DB_SESSION()
            # Generate Unique Trade Code
            trade_count = session.query(Trade).filter(Trade.symbol == symbol).count()
            side_code = "L" if side.upper() == "BUY" else "S"
            trade_code = f"{symbol.split('USDT')[0]}-{side_code}-{trade_count+1:02d}"

            new_trade = Trade(
                symbol=symbol, side=side, amount=amount, entry_price=price,
                entry_time=datetime.utcnow(), status="OPEN", order_id=result["order_id"],
                strategy="STRATEGIC_BRIDGE", leverage=1, trade_code=trade_code
            )
            session.add(new_trade)
            session.commit()

            ACTIVE_TRADES.append({
                "id": new_trade.id, 
                "trade_code": trade_code,
                "time": new_trade.entry_time.timestamp(),
                "symbol": symbol, 
                "type": f"{side.upper()} (STRATEGIC)", 
                "status": "OPEN",
                "pnl": "$0.00", 
                "cost": f"${(amount * price):.2f}",
                "entry_price": price,
                "amount": amount,
                "order_id": new_trade.order_id, 
                "reason": "STRATEGIC_BRIDGE",
                "conviction": "95%", 
                "risk": "LOW", 
                "leverage": 1
            })

            logger.success(f"STRATEGIC SUCCESS: {symbol} pos opened via {decision_data['reason']}")
            session.close()
            return True
        else:
            logger.error(f"STRATEGIC FAILURE: Execution rejected: {result.get('reason')}")
            return False
