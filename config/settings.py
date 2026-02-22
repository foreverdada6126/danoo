from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "DaNoo"
    VERSION: str = "5.2.0"
    
    # Operational Modes
    # 'paper' - auto execute, no confirmation
    # 'real' - manual confirmation via telegram
    MODE: str = os.getenv("APP_MODE", "paper")
    
    # Exchange Config
    EXCHANGE_ID: str = os.getenv("EXCHANGE_ID", "bybit")
    DEFAULT_SYMBOL: str = "BTCUSDT"
    DEFAULT_TIMEFRAME: str = "15m"
    
    # Path Config
    DATA_PATH: str = "data"
    DB_PATH: str = "database/memory.db"
    LOG_PATH: str = "logs"
    
    # API Keys & Webhooks
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")
    MISSION_CONTROL_WEBHOOK: Optional[str] = os.getenv("MISSION_CONTROL_WEBHOOK")
    LOCAL_AUTH_TOKEN: Optional[str] = os.getenv("LOCAL_AUTH_TOKEN")
    
    # Exchange Secrets
    BINANCE_API_KEY: Optional[str] = os.getenv("BINANCE_API_KEY")
    BINANCE_SECRET: Optional[str] = os.getenv("BINANCE_SECRET")
    BYBIT_API_KEY: Optional[str] = os.getenv("BYBIT_API_KEY")
    BYBIT_SECRET: Optional[str] = os.getenv("BYBIT_SECRET")
    USE_SANDBOX: bool = os.getenv("USE_SANDBOX", "true").lower() == "true"
    
    # Telegram Config
    TELEGRAM_TOKEN: Optional[str] = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = True

SETTINGS = Settings()
