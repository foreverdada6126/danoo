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
    EXCHANGE_ID: str = "binance"
    DEFAULT_SYMBOL: str = "BTCUSDT"
    DEFAULT_TIMEFRAME: str = "15m"
    
    # Path Config
    DATA_PATH: str = "data"
    DB_PATH: str = "database/memory.db"
    LOG_PATH: str = "logs"
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")

    class Config:
        env_file = "config/secrets.env"
        case_sensitive = True

SETTINGS = Settings()
