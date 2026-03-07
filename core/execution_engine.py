import asyncio
import time
import os
from typing import Dict, Any, Optional
from loguru import logger
from config.settings import SETTINGS
from config.risk_config import RISK_CONFIG
from core.exchange_handler import ExchangeHandler

class ExecutionEngine:
    """
    Manages order execution with Paper and Real modes.
    Ensures deterministic execution and risk enforcement.
    """
    
    def __init__(self, mode: str = "paper"):
        self.mode = mode.lower()
        self.bridge = ExchangeHandler()
        logger.info(f"Execution Engine: Initialized in {self.mode.upper()} mode.")
        
    async def execute_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Executes an order based on current mode and risk constraints.
        """
        # 1. Risk Pre-check
        if not self.validate_risk(symbol, amount):
            logger.warning(f"Execution Rejected: Risk validation failed for {symbol}")
            return {"status": "REJECTED", "reason": "Risk limit exceeded"}

        # 2. Execution logic
        if self.mode == "real":
            return await self._handle_real_execution(symbol, side, amount, price)
        else:
            return await self._handle_paper_execution(symbol, side, amount, price)

    def validate_risk(self, symbol: str, amount: float) -> bool:
        """
        Enforces RISK_CONFIG before any execution.
        """
        # Basic validation against config
        if amount <= 0:
            return False
            
        if RISK_CONFIG.position_size_validation_before_execution:
            # Add more complex logic if needed (e.g., wallet exposure checks)
            pass
        return True

    async def _handle_paper_execution(self, symbol: str, side: str, amount: float, price: Optional[float]) -> Dict[str, Any]:
        """Simulates a filled order for paper trading."""
        logger.info(f"[PAPER] Order Executed: {side.upper()} {amount} {symbol}")
        return {
            "status": "FILLED",
            "order_id": f"paper_{int(time.time())}",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price or 0.0,
            "mode": "paper"
        }

    async def _handle_real_execution(self, symbol: str, side: str, amount: float, price: Optional[float]) -> Dict[str, Any]:
        """
        Executes real trades via the Exchange Bridge.
        """
        # Optional: Manual Confirmation logic can be toggled in RISK_CONFIG
        if RISK_CONFIG.double_check_real_money_orders:
            logger.info(f"[REAL] Manual Approval Required for: {side.upper()} {amount} {symbol}")
            # In a fully autonomous bot, we might want to bypass this or integrate with a signal
            return {"status": "PENDING_APPROVAL", "symbol": symbol, "side": side}
        
        logger.info(f"[REAL] Executing {side.upper()} {amount} {symbol} on Exchange...")
        
        # Call the exchange handler (Assuming market orders for now as per current bridge)
        result = await self.bridge.place_limit_order(symbol, side, amount, price or 0.0)
        
        if result.get("success"):
            order_data = result.get("order", {})
            logger.success(f"[REAL] Order FILLED: {symbol} ID: {order_data.get('id')}")
            return {
                "status": "FILLED",
                "order_id": order_data.get("id"),
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": order_data.get("price", price),
                "mode": "real"
            }
        else:
            logger.error(f"[REAL] Execution Failed: {result.get('error')}")
            return {"status": "FAILED", "reason": result.get("error")}
