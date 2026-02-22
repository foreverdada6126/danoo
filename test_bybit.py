import asyncio
import os
from dotenv import load_dotenv

# Load any .env variables
load_dotenv()

# We force the mode for Bybit explicitly just for this test
os.environ["EXCHANGE_ID"] = "bybit"
os.environ["USE_SANDBOX"] = "true"

from core.exchange_handler import ExchangeHandler

async def test_bybit():
    print("Testing ByBit Integration...")
    handler = ExchangeHandler()
    
    # Try fetching market data and balance to see if the connection is working
    market_data = await handler.fetch_market_data("BTC/USDT:USDT", "15m")
    print("Market Data:", market_data)
    
    # We will close the client internally or let it finish
    await handler.client.close()
    print("Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_bybit())
