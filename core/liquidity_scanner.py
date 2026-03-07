import asyncio
import numpy as np
from loguru import logger
from core.exchange_handler import ExchangeHandler

class LiquidityScanner:
    """
    DaNoo Institutional: Deep Order Book Scan.
    Identifies 'Whale Walls' and 'Liquidity Pools' to filter low-probability trades.
    Only enters when institutional liquidity is positioned to support the move.
    """
    def __init__(self):
        self.bridge = ExchangeHandler()

    async def scan_symbol(self, symbol):
        """
        Analyzes the top 100 limit orders on both sides to find significant liquidity walls.
        """
        try:
            client = await self.bridge._get_client(force_public=True)
            # Fetch deeper L2 Order Book (Depth)
            orderbook = await client.fetch_order_book(symbol, limit=250)
            
            bids = np.array(orderbook['bids']) # [price, amount]
            asks = np.array(orderbook['asks'])
            
            if len(bids) < 5 or len(asks) < 5:
                logger.warning(f"Thin Order Book [{symbol}]: Bids={len(bids)}, Asks={len(asks)}")
                return None

            current_price = bids[0][0]
            
            # 1. Identify "Whale Walls" (Price levels with HUGE volume)
            # Filter extremely small dust to get a cleaner average
            clean_bids = bids[bids[:, 1] > np.percentile(bids[:, 1], 20)]
            clean_asks = asks[asks[:, 1] > np.percentile(asks[:, 1], 20)]
            
            avg_bid_size = np.mean(clean_bids[:, 1])
            avg_ask_size = np.mean(clean_asks[:, 1])
            
            # Find bins where size > 2.0x average (The Walls) - Lowered from 3.0x
            bid_walls = bids[bids[:, 1] > (avg_bid_size * 2.0)]
            ask_walls = asks[asks[:, 1] > (avg_ask_size * 2.0)]
            
            # 2. Institutional Imbalance
            total_bid_liq = np.sum(bids[:, 1] * bids[:, 0])
            total_ask_liq = np.sum(asks[:, 1] * asks[:, 0])
            imbalance = (total_bid_liq - total_ask_liq) / (total_bid_liq + total_ask_liq + 1e-10)
            
            # 3. Find "Golden Liquidity" (The single strongest support/resistance)
            support = bid_walls[np.argmax(bid_walls[:, 1])][0] if len(bid_walls) > 0 else bids[-1][0]
            resistance = ask_walls[np.argmax(ask_walls[:, 1])][0] if len(ask_walls) > 0 else asks[-1][0]
            
            # Reliability Score: How close are we to a major wall?
            # Higher score = Price is sitting on a wall = "Guaranteed" Bounce
            dist_to_support = (current_price - support) / current_price
            dist_to_res = (resistance - current_price) / current_price
            
            return {
                "symbol": symbol,
                "price": current_price,
                "support": support,
                "resistance": resistance,
                "bid_walls": len(bid_walls),
                "ask_walls": len(ask_walls),
                "imbalance": round(imbalance, 4),
                "is_whale_support": dist_to_support < 0.002, # within 0.2% of a wall
                "is_whale_resistance": dist_to_res < 0.002
            }
            
        except Exception as e:
            logger.error(f"Liquidity Scan Error [{symbol}]: {e}")
            return None

LIQUIDITY_SCANNER = LiquidityScanner()
