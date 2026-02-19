from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config.settings import SETTINGS

Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False) # LONG, SHORT
    entry_price = Column(Float)
    exit_price = Column(Float)
    amount = Column(Float)
    leverage = Column(Integer, default=1)
    status = Column(String, default='OPEN') # OPEN, CLOSED, REJECTED
    pnl = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    regime = Column(String)
    strategy = Column(String)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime)
    order_id = Column(String)

class CandleCache(Base):
    """Local cache for high-speed signal calculation."""
    __tablename__ = 'candle_cache'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timeframe = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class StrategyPerformance(Base):
    """Long-term memory for AI Meta Review."""
    __tablename__ = 'strategy_performance'
    
    id = Column(Integer, primary_key=True)
    strategy_name = Column(String)
    regime = Column(String)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    avg_pnl = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)

# Database initialization helper
def init_db():
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{SETTINGS.DB_PATH}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

DB_SESSION = init_db()
