"""
DaNoo MCP Server - v1.0 [Autonomous Bridge]
Connects DaNoo Engine to Claude Desktop / Model Context Protocol.
"""
import sys
import json
import asyncio
from loguru import logger
from core.exchange_handler import ExchangeHandler
from core.execution_engine import ExecutionEngine
from web_ui.state import SYSTEM_STATE, LOG_HISTORY
from config.settings import SETTINGS

async def get_bot_status():
    """Returns the current state of the DaNoo engine."""
    return {
        "regime": SYSTEM_STATE.get("regime", "UNKNOWN"),
        "sentiment": SYSTEM_STATE.get("sentiment_score", 0.0),
        "equity": SYSTEM_STATE.get("equity", 0.0),
        "symbol": SYSTEM_STATE.get("symbol", "BTCUSDT"),
        "active_orders": SYSTEM_STATE.get("active_orders", 0)
    }

async def get_market_data(symbol: str):
    """Fetches real-time price and technical context for a specific symbol."""
    bridge = ExchangeHandler()
    client = await bridge._get_client(force_public=True)
    ticker = await client.fetch_ticker(symbol)
    return {
        "symbol": symbol,
        "price": ticker.get("last"),
        "high": ticker.get("high"),
        "low": ticker.get("low"),
        "vol": ticker.get("baseVolume")
    }

async def execute_trade_tool(symbol: str, side: str, amount: float):
    """Triggers an order via the ExecutionEngine."""
    executor = ExecutionEngine(mode="paper") # Forces paper for safety via MCP initially
    price_res = await get_market_data(symbol)
    price = price_res.get("price")
    
    logger.info(f"MCP COMMAND: Executing {side.upper()} for {amount} {symbol}...")
    result = await executor.execute_order(symbol, side, amount, price)
    return result

async def main():
    """Simple STDIO-based MCP Server loop."""
    logger.remove() # Clean logs for stdio
    logger.add(sys.stderr, level="INFO")
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            result = None
            
            if method == "get_bot_status":
                result = await get_bot_status()
            elif method == "get_market_data":
                result = await get_market_data(params.get("symbol", "BTCUSDT"))
            elif method == "execute_trade":
                result = await execute_trade_tool(
                    params.get("symbol"), 
                    params.get("side"), 
                    params.get("amount")
                )
            elif method == "read_logs":
                result = LOG_HISTORY[-10:] if LOG_HISTORY else [{"msg": "No logs available"}]
            else:
                result = {"error": "Method not found"}
                
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except Exception as e:
            error_resp = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
