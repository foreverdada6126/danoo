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
            
            bids = np.array(orderbook['bids']) if orderbook.get('bids') else np.array([])
            asks = np.array(orderbook['asks']) if orderbook.get('asks') else np.array([])
            
            if len(bids) < 5 or len(asks) < 5:
                logger.warning(f"Thin Order Book [{symbol}]: Bids={len(bids)}, Asks={len(asks)}")
                return None

            current_price = bids[0][0]
            
            # 1. Identify "Whale Walls" (Price levels with HUGE volume)
            # Use Median as a more stable baseline for "Normal" order size
            median_bid = np.median(bids[:, 1])
            median_ask = np.median(asks[:, 1])
            
            # Walls are orders significant enough to stall or bounce price
            # We look for orders > 1.8x the median (Lowered for higher sensitivity)
            bid_walls = bids[bids[:, 1] > (median_bid * 1.8)]
            ask_walls = asks[asks[:, 1] > (median_ask * 1.8)]
            
            # 2. Institutional Imbalance
            total_bid_liq = np.sum(bids[:, 1] * bids[:, 0])
            total_ask_liq = np.sum(asks[:, 1] * asks[:, 0])
            imbalance = (total_bid_liq - total_ask_liq) / (total_bid_liq + total_ask_liq + 1e-10)
            
            # 3. Find "Golden Liquidity" (The single strongest support/resistance)
            support = bid_walls[np.argmax(bid_walls[:, 1])][0] if len(bid_walls) > 0 else bids[-1][0]
            resistance = ask_walls[np.argmax(ask_walls[:, 1])][0] if len(ask_walls) > 0 else asks[-1][0]
            
            # Proximity check
            dist_to_support = (current_price - support) / current_price
            dist_to_res = (resistance - current_price) / current_price
            
            return {
                "symbol": symbol,
                "price": current_price,
                "support": float(support),
                "resistance": float(resistance),
                "bid_walls": int(len(bid_walls)),
                "ask_walls": int(len(ask_walls)),
                "imbalance": round(float(imbalance), 4),
                "is_whale_support": bool(dist_to_support < 0.003), # 0.3% zone
                "is_whale_resistance": bool(dist_to_res < 0.003),
                "timestamp": time.time()
            }
            
        except Exception as e:
            if "rate limit" in str(e).lower():
                logger.error(f"BYBIT RATE LIMIT HIT while scanning {symbol}. Throttling required.")
            else:
                logger.error(f"Liquidity Scan Error [{symbol}]: {e}")
            return None

LIQUIDITY_SCANNER = LiquidityScanner()
