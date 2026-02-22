"""
Trade Routes - Active trades, trade history, approvals, close positions.
"""
import time
from fastapi import APIRouter
from loguru import logger
from config.settings import SETTINGS
from database.models import DB_SESSION, Trade
from web_ui.state import SYSTEM_STATE, LOG_HISTORY, ACTIVE_TRADES, APPROVAL_QUEUE
from datetime import datetime

router = APIRouter()

@router.get("/api/system/trades")
async def get_active_trades():
    """Returns active trades with real-time PnL calculations."""
    from core.exchange_handler import ExchangeHandler
    
    price_cache = {}
    
    async def get_price(symbol):
        if symbol in price_cache:
            return price_cache[symbol]
        try:
            bridge = ExchangeHandler()
            # Force Public for Real Prices in Dashboard
            client = await bridge._get_client(force_public=True)
            ticker = await client.fetch_ticker(symbol)
            price_cache[symbol] = ticker.get("last", 0.0)
            return price_cache[symbol]
        except:
            if symbol == SYSTEM_STATE.get("symbol", "BTCUSDT"):
                return SYSTEM_STATE.get("price", 0.0)
            return 0.0
    
    for t in ACTIVE_TRADES:
        try:
            session = DB_SESSION()
            db_t = session.query(Trade).filter(Trade.id == t["id"]).first()
            if db_t:
                current_price = await get_price(db_t.symbol)
                if db_t.entry_price and current_price > 0:
                    side_mult = 1 if db_t.side.upper() in ["BUY", "LONG"] else -1
                    raw_pnl = (current_price - db_t.entry_price) * db_t.amount * side_mult
                    t["pnl"] = f"{'+' if raw_pnl >= 0 else ''}${raw_pnl:.2f}"
                    t["cost"] = f"${(db_t.entry_price * db_t.amount):.2f}"
                    t["value"] = f"${(current_price * db_t.amount):.2f}"
                t["leverage"] = db_t.leverage or 1
            session.close()
        except:
            pass
            
    return {"trades": ACTIVE_TRADES}

@router.get("/api/system/trades/all")
async def get_all_trades():
    """Returns all trades (opened and closed) from the database."""
    from core.exchange_handler import ExchangeHandler
    
    try:
        session = DB_SESSION()
        db_trades = session.query(Trade).order_by(Trade.entry_time.desc()).limit(50).all()
        result = []
        
        # Cache prices for live PnL on open trades
        price_cache = {}
        
        async def get_price(symbol):
            if symbol in price_cache:
                return price_cache[symbol]
            try:
                bridge = ExchangeHandler()
                client = await bridge._get_client(force_public=True)
                ticker = await client.fetch_ticker(symbol)
                price_cache[symbol] = ticker.get("last", 0.0)
                return price_cache[symbol]
            except:
                return 0.0
        
        for t in db_trades:
            strat_name = t.strategy or "Auto Trade"
            conviction = "95%" if "STRICT" in strat_name else ("70%" if "LOOSE" in strat_name else ("85%" if "RECON" in strat_name else "N/A"))
            risk = "LOW" if "STRICT" in strat_name else ("MED" if "LOOSE" in strat_name else ("HIGH" if "RECON" in strat_name else "UNK"))
            
            # Calculate live PnL for open trades
            cost_val = (t.entry_price or 0) * (t.amount or 0)
            if t.status == "OPEN" and t.entry_price and t.amount:
                current_price = await get_price(t.symbol)
                if current_price > 0:
                    side_mult = 1 if t.side.upper() in ["BUY", "LONG"] else -1
                    raw_pnl = (current_price - t.entry_price) * t.amount * side_mult
                    pnl_str = f"{'+' if raw_pnl >= 0 else ''}${raw_pnl:.2f}"
                else:
                    pnl_str = "$0.00"
            else:
                pnl_str = f"${(t.pnl or 0.0):.2f}"
            
            result.append({
                "id": t.id,
                "time": t.entry_time.timestamp(),
                "symbol": t.symbol,
                "type": f"{t.side.upper()}",
                "status": t.status,
                "pnl": pnl_str,
                "cost": f"${cost_val:.2f}",
                "order_id": t.order_id,
                "reason": strat_name,
                "conviction": conviction,
                "risk": risk,
                "leverage": t.leverage or 1
            })
        session.close()
        return {"trades": result}
    except Exception as e:
        logger.error(f"Error fetching trade history: {e}")
        return {"trades": []}

@router.get("/api/system/approvals")
async def get_approval_queue():
    return {"approvals": APPROVAL_QUEUE}

@router.post("/api/system/close/{order_id}")
async def close_trade(order_id: str):
    """Closes an active position and updates the database."""
    from web_ui.state import TRADE_LOG_HISTORY
    from core.exchange_handler import ExchangeHandler
    try:
        trade = next((t for t in ACTIVE_TRADES if t["order_id"] == order_id), None)
        if not trade:
            return {"status": "error", "message": "Trade not found in active memory."}

        is_paper = order_id.startswith("paper_") or SETTINGS.MODE == "paper"
        
        # Determine exit price
        try:
            bridge = ExchangeHandler()
            client = await bridge._get_client()
            ticker = await client.fetch_ticker(trade["symbol"])
            exit_price = ticker.get("last", 0.0)
            await bridge.close()
        except:
            exit_price = SYSTEM_STATE.get("price", 0.0)

        if not is_paper:
            # Real trade: send close order to exchange
            session = DB_SESSION()
            db_trade = session.query(Trade).filter(Trade.order_id == order_id).first()
            if not db_trade:
                session.close()
                return {"status": "error", "message": "Trade not found in database."}
            actual_amount = db_trade.amount
            session.close()

            bridge = ExchangeHandler()
            side = "sell" if "LONG" in trade["type"].upper() or "BUY" in trade["type"].upper() else "buy"
            
            logger.info(f"Closing Trade {order_id} via Market {side.upper()} {actual_amount}...")
            result = await bridge.place_limit_order(
                symbol=trade["symbol"],
                side=side,
                amount=actual_amount,
                price=0 
            )
            await bridge.close()

            if not result["success"]:
                return {"status": "error", "message": f"Exchange Failed to Close: {result.get('error')}"}

        # Update database (both paper and real)
        final_pnl = 0.0
        try:
            session = DB_SESSION()
            db_t = session.query(Trade).filter(Trade.order_id == order_id).first()
            if db_t:
                db_t.status = "CLOSED"
                db_t.exit_time = datetime.utcnow()
                db_t.exit_price = exit_price
                
                if db_t.entry_price and db_t.amount:
                    side_mult = 1 if db_t.side.upper() in ["BUY", "LONG"] else -1
                    final_pnl = (exit_price - db_t.entry_price) * db_t.amount * side_mult
                    db_t.pnl = final_pnl
                
                session.commit()
                
                # Specialized Trade Log for Intelligence
                TRADE_LOG_HISTORY.append({
                    "timestamp": time.time(),
                    "action": "EXIT",
                    "symbol": trade["symbol"],
                    "type": trade["type"],
                    "price": exit_price,
                    "amount": db_t.amount,
                    "leverage": db_t.leverage or 1,
                    "pnl": final_pnl,
                    "reason": "MANUAL_CLOSE"
                })
            session.close()
        except Exception as db_err:
            logger.error(f"DB Error during closure: {db_err}")

        ACTIVE_TRADES.remove(trade)
        close_type = "PAPER" if is_paper else "EXCHANGE"
        LOG_HISTORY.append({"time": time.time(), "msg": f"{close_type}: Successfully closed position {order_id}."})
        return {"status": "success", "message": f"Trade {order_id} closed."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/system/approve/{signal_id}")
async def approve_trade(signal_id: int):
    """Approves a pending trade signal and executes on the exchange."""
    from core.exchange_handler import ExchangeHandler
    try:
        if 0 <= signal_id < len(APPROVAL_QUEUE):
            approved = APPROVAL_QUEUE.pop(signal_id)
            
            bridge = ExchangeHandler()
            side = "buy" if "LONG" in approved["signal"].upper() else "sell"
            
            result = await bridge.place_limit_order(
                symbol=SETTINGS.DEFAULT_SYMBOL, 
                side=side, 
                amount=0.001, 
                price=SYSTEM_STATE.get("price", 50000) 
            )

            if result["success"]:
                order = result["order"]
                
                try:
                    session = DB_SESSION()
                    db_trade = Trade(
                        symbol=SETTINGS.DEFAULT_SYMBOL,
                        side=side.upper(),
                        entry_price=SYSTEM_STATE.get("price", 0.0),
                        amount=0.001,
                        status="OPEN",
                        order_id=order['id'],
                        strategy=approved.get("reason", "AI Signal")
                    )
                    session.add(db_trade)
                    session.commit()
                    trade_id = db_trade.id
                    session.close()
                except Exception as db_err:
                    logger.error(f"DB Error during approval: {db_err}")
                    trade_id = int(time.time())

                new_trade = {
                    "id": trade_id,
                    "time": time.time(),
                    "symbol": SETTINGS.DEFAULT_SYMBOL,
                    "type": f"{side.upper()} (REAL)",
                    "status": "OPEN",
                    "pnl": "+$0.00",
                    "order_id": order['id'],
                    "reason": approved.get("reason", "Manual Confirmation")
                }
                ACTIVE_TRADES.insert(0, new_trade)
                
                current_balance = await bridge.fetch_balance()
                await bridge.close()
                if current_balance is not None:
                    SYSTEM_STATE["equity"] = current_balance
                LOG_HISTORY.append({"time": time.time(), "msg": f"EXCHANGE: Order {order['id']} placed successfully."})
                return {"status": "success", "message": f"Trade {order['id']} executed."}
            else:
                await bridge.close()
                APPROVAL_QUEUE.insert(signal_id, approved)
                return {"status": "error", "message": f"Exchange Rejected: {result.get('error')}"}
                
        return {"status": "error", "message": "Signal not found."}
    except Exception as e:
        logger.error(f"Approval Error: {e}")
        return {"status": "error", "message": str(e)}
@router.get("/api/trade_logs")
async def get_trade_logs():
    """Returns the history of recent trade execution events."""
    from web_ui.state import TRADE_LOG_HISTORY
    return {"logs": TRADE_LOG_HISTORY[-50:]} # Return last 50 events
