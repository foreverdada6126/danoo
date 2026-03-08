from sqlalchemy import desc
from database.models import DB_SESSION, Trade
from loguru import logger
from datetime import datetime
import json

class TradeAnalyzer:
    """
    Expert Analytics Engine for Trade Review and Optimization.
    """
    
    @staticmethod
    async def analyze_asset(symbol: str, count: int = 5):
        """
        Fetches last X trades for an asset and generates a detailed performance audit.
        """
        if "USDT" not in symbol: symbol += "USDT"
        
        session = DB_SESSION()
        try:
            trades = session.query(Trade).filter(Trade.symbol == symbol)\
                .order_by(desc(Trade.entry_time)).limit(count).all()
            
            if not trades:
                return f"🔍 **Analysis for {symbol}:** No trade history found in the database. Deploy more capital!"

            report = [f"📊 **Expert Audit: {symbol} (Last {len(trades)} Trades)**\n"]
            
            total_pnl = 0
            wins = 0
            
            for t in trades:
                status_icon = "🟢" if t.status == "OPEN" else ("💰" if t.pnl > 0 else "🛑")
                pnl_str = f"${t.pnl:.2f}" if t.pnl is not None else "PENDING"
                
                # Extract Market Context
                ctx = t.market_context if t.market_context else {}
                rsi = ctx.get("rsi", "N/A")
                liq = ctx.get("liquidity", {})
                imbalance = liq.get("imbalance", 0) if liq else 0
                
                # Logic: Improvement suggestions
                optimization = "Maintain current strategy."
                if t.pnl and t.pnl < 0:
                    if float(rsi) > 70 and t.side == "BUY":
                        optimization = "WARNING: Entry was overbought. Lower RSI threshold for LONGs."
                    elif float(rsi) < 30 and t.side == "SELL":
                        optimization = "WARNING: Entry was oversold. Raise RSI threshold for SHORTs."
                    elif abs(imbalance) < 0.1:
                        optimization = "IMPROVEMENT: Entrance lacked strong institutional imbalance. Increase conviction filter."
                
                trade_report = (
                    f"---"
                    f"\n**Trade:** `{t.trade_code}` | {t.side} | {status_icon} **{pnl_str}**"
                    f"\n**Reason:** {t.strategy}"
                    f"\n**Context at Entry:** RSI: `{rsi}` | Imbalance: `{imbalance:.2f}`"
                    f"\n**Audit Note:** {optimization}\n"
                )
                report.append(trade_report)
                
                if t.pnl:
                    total_pnl += t.pnl
                    if t.pnl > 0: wins += 1
            
            win_rate = (wins / len([t for t in trades if t.pnl is not None])) * 100 if trades else 0
            summary = (
                f"\n**--- TOTAL SUMMARY ---**"
                f"\n📈 **Win Rate:** {win_rate:.1f}%"
                f"\n💵 **Cumulative PnL:** ${total_pnl:.2f}"
                f"\n💡 **Expert Advice:** {'Strategy is stable. Scaling recommended.' if total_pnl > 0 else 'Refining liquidity filters to avoid high-slippage entries.'}"
            )
            report.append(summary)
            
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"Analysis Error: {e}")
            return f"❌ Analysis Error: {str(e)}"
        finally:
            session.close()

TRADING_AUDITOR = TradeAnalyzer()
