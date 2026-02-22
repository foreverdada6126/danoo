"""
Chart Routes - OHLCV data, equity history, trade markers.
"""
from fastapi import APIRouter
from loguru import logger
from database.models import DB_SESSION, Trade
from web_ui.state import SYSTEM_STATE, EQUITY_HISTORY

router = APIRouter()

@router.get("/api/chart")
async def get_chart_data():
    """Returns the history of equity for the Performance chart."""
    if not EQUITY_HISTORY or EQUITY_HISTORY[-1] != SYSTEM_STATE["equity"]:
        EQUITY_HISTORY.append(SYSTEM_STATE["equity"])
    
    history = EQUITY_HISTORY[-50:]
    return {
        "labels": [f"T-{len(history)-i-1}" for i in range(len(history))],
        "values": history
    }

@router.get("/api/chart/ohlcv")
async def get_ohlcv_data(symbol: str = "BTCUSDT", timeframe: str = "15m"):
    """Returns OHLCV candles and trade markers for the price chart."""
    from core.exchange_handler import ExchangeHandler
    
    candles = []
    trades = []
    
    try:
        bridge = ExchangeHandler()
        client = await bridge._get_client()
        ohlcv = await client.fetch_ohlcv(symbol, timeframe, limit=200)
        
        candles = [{
            "time": int(row[0] / 1000),
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
        } for row in ohlcv]
        
        session = DB_SESSION()
        db_trades = session.query(Trade).filter(Trade.symbol == symbol).order_by(Trade.entry_time.desc()).limit(50).all()
        
        candle_times = [c["time"] for c in candles]
        
        def snap_time(t):
            if not candle_times: return t
            valid_times = [ct for ct in candle_times if ct <= t]
            return max(valid_times) if valid_times else candle_times[0]
        
        for t in db_trades:
            entry_time = int(t.entry_time.timestamp()) if t.entry_time else None
            if entry_time:
                snapped_entry = snap_time(entry_time)
                marker = {
                    "time": snapped_entry,
                    "position": "belowBar" if t.side.upper() in ["BUY", "LONG"] else "aboveBar",
                    "color": "#00f2ff" if t.side.upper() in ["BUY", "LONG"] else "#f23645",
                    "shape": "arrowUp" if t.side.upper() in ["BUY", "LONG"] else "arrowDown",
                    "text": f"{t.side[:1]} @ {t.entry_price:.2f}" if t.entry_price else t.side,
                }
                trades.append(marker)
            
            if t.exit_time and t.exit_price:
                exit_time = int(t.exit_time.timestamp())
                snapped_exit = snap_time(exit_time)
                exit_marker = {
                    "time": snapped_exit,
                    "position": "aboveBar" if t.side.upper() in ["BUY", "LONG"] else "belowBar",
                    "color": "#22ab94" if t.pnl and t.pnl >= 0 else "#f23645",
                    "shape": "circle",
                    "text": f"Exit @ {t.exit_price:.2f}",
                }
                trades.append(exit_marker)
        
        trades.sort(key=lambda x: x["time"])
        session.close()
        
    except Exception as e:
        logger.error(f"Chart data fetch error: {e}")
    
    return {"candles": candles, "trades": trades}
