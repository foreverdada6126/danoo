"""
DaNoo v5.4 - System Purge & Reset Utility
Usage: python purge.py
"""
import os
import shutil
from sqlalchemy import create_engine
from database.models import Base
from config.settings import SETTINGS
from loguru import logger

def purge_database():
    """Drops and recreates the tables to clear all trade history."""
    try:
        db_path = SETTINGS.DB_PATH
        if os.path.exists(db_path):
            logger.info(f"Purging Database: {db_path}...")
            engine = create_engine(f"sqlite:///{db_path}")
            # Drop all tables
            Base.metadata.drop_all(engine)
            # Recreate all tables
            Base.metadata.create_all(engine)
            logger.success("Database purged and schema reset successfully.")
        else:
            logger.warning(f"Database not found at {db_path}. Creating new one.")
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(engine)
    except Exception as e:
        logger.error(f"Failed to purge database: {e}")

def purge_logs():
    """Clears all log files in the log directory."""
    log_dir = SETTINGS.LOG_PATH
    if os.path.exists(log_dir):
        logger.info(f"Purging Logs in {log_dir}...")
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}. Reason: {e}")
        logger.success("Logs cleared successfully.")
    else:
        logger.warning(f"Log directory {log_dir} not found.")

if __name__ == "__main__":
    print("====================================")
    print("   DaNoo SYSTEM PURGE & RESET       ")
    print("====================================")
    purge_database()
    purge_logs()
    print("\n[SUCCESS] System reset to factory clean state.")
    print("[INFO] Please restart DaNoo to apply changes.")
