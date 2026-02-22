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
    from web_ui.state import INTELLIGENCE_FLOW
    import time
    
    candles = []
    trades = []
    
    try:
        bridge = ExchangeHandler()
        client = await bridge._get_client()
        ohlcv = await client.fetch_ohlcv(symbol, timeframe, limit=200)
        await bridge.close()
        
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
                    "color": "#089981" if t.side.upper() in ["BUY", "LONG"] else "#f23645",
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
                    "color": "#fff" if t.pnl and t.pnl >= 0 else "#f23645",
                    "shape": "circle",
                    "text": f"Exit @ {t.exit_price:.2f}",
                }
                trades.append(exit_marker)
        
        trades.sort(key=lambda x: x["time"])
        session.close()
        
        # Intelligence Logging
        INTELLIGENCE_FLOW.append({
            "timestamp": time.time(),
            "cat": "CHART",
            "msg": f"Synchronized {len(candles)} candles for {symbol} ({timeframe}). Loaded {len(trades)} trade markers."
        })
        if len(INTELLIGENCE_FLOW) > 100: INTELLIGENCE_FLOW.pop(0)
        
    except Exception as e:
        logger.error(f"Chart data fetch error: {e}")
        INTELLIGENCE_FLOW.append({
            "timestamp": time.time(),
            "cat": "ERROR",
            "msg": f"Chart Sync Fail: {symbol} - {str(e)}"
        })
    
    return {"candles": candles, "trades": trades}

@router.get("/api/market/prices")
async def get_all_prices():
    """Returns live prices for all supported assets."""
    from core.exchange_handler import ExchangeHandler
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "HBARUSDT", "DOGEUSDT", "XLMUSDT", "XDCUSDT"]
    prices = {}
    try:
        bridge = ExchangeHandler()
        client = await bridge._get_client()
        tickers = await client.fetch_tickers(symbols)
        for s in symbols:
            if s in tickers:
                prices[s] = tickers[s].get("last", 0.0)
        await bridge.close()
    except Exception as e:
        logger.error(f"Multi-price fetch error: {e}")
    return {"prices": prices}
