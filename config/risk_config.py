from pydantic import BaseModel

class RiskConfig(BaseModel):
    # Core Risk Parameters
    max_risk_per_trade: float = 0.01          # 1% of equity
    max_portfolio_drawdown: float = 0.10      # 10% halt limit
    automatic_deleveraging: bool = True
    stablecoin_fallback: bool = True
    kill_switch_on_extreme_volatility: bool = True
    
    # Execution Constraints
    min_order_size_usdt: float = 10.0
    max_leverage: int = 20
    
    # Circuit Breakers
    circuit_breaker_price_gap_pct: float = 0.05 # 5% gap halts trading
    
    # Security
    position_size_validation_before_execution: bool = True
    double_check_real_money_orders: bool = True

RISK_CONFIG = RiskConfig()
