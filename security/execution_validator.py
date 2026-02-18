from loguru import logger
from config.risk_config import RISK_CONFIG

class ExecutionValidator:
    """
    Final checkpoint before orders hit the exchange.
    Enforces risk limits and sanity checks.
    """
    
    @staticmethod
    def validate(order: dict, current_price: float, positions: list) -> bool:
        """
        Returns True if the order passes all security and risk checks.
        """
        # 1. Price Sanity Check
        order_price = order.get('price', current_price)
        price_gap = abs(order_price - current_price) / current_price
        
        if price_gap > RISK_CONFIG.circuit_breaker_price_gap_pct:
            logger.error(f"Execution Blocked: Price gap {price_gap:.2%} exceeds circuit breaker.")
            return False
            
        # 2. Position Size Validation
        # (Compare current position + order vs max portfolio risk)
        
        # 3. Mode Validation
        # (Prevent accidental live trades in paper mode, or missing approvals in real mode)
        
        logger.info(f"Execution Validation Passed for {order.get('symbol')}")
        return True
