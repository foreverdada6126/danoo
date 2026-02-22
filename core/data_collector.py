import os
import aiohttp
import aiofiles
import zipfile
import pandas as pd
from loguru import logger
from typing import List, Optional

class HistoricalDataCollector:
    """
    Ported & Optimized from the Historical-Market-Data-Collector-CSV-Based-Multi-Year repository.
    Fetches bulk historical market data from Binance Public Archives bypassing REST API rate limits.
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        # We target UM Futures by default since DaNoo is a futures scalper
        self.url_base = 'https://data.binance.vision/data/futures/um/monthly/klines'

    async def collect_async(self, symbol: str, interval: str, start_year: int, end_year: int) -> Optional[str]:
        """Asynchronously downloads, extracts, and merges CSV data for the specified years."""
        years = list(range(start_year, end_year + 1))
        dfs = []
        
        logger.info(f"Data Collector: Initiating bulk fetch for {symbol} ({interval}) {start_year}-{end_year}")
        
        async with aiohttp.ClientSession() as session:
            for y in years:
                for m in range(1, 13):
                    fn = f"{symbol}-{interval}-{y}-{m:02d}"
                    url = f"{self.url_base}/{symbol}/{interval}/{fn}.zip"
                    
                    try:
                        async with session.get(url) as r:
                            if r.status != 200:
                                continue
                            
                            zip_path = os.path.join(self.data_dir, f"{fn}.zip")
                            
                            # Write zip file asynchronously
                            async with aiofiles.open(zip_path, 'wb') as f:
                                await f.write(await r.read())
                            
                            # Extract synchronously (blocking but fast)
                            csv_path = os.path.join(self.data_dir, f"{fn}.csv")
                            with zipfile.ZipFile(zip_path, 'r') as z:
                                z.extractall(self.data_dir)
                            
                            # Read into Pandas
                            df = pd.read_csv(csv_path, header=None)
                            df.columns = ['timestamp','open','high','low','close','volume',
                                          'close_time','quote_volume','trades',
                                          'taker_base_vol','taker_quote_vol','ignore']
                            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                            dfs.append(df)
                            
                            # Cleanup temporary files
                            os.remove(zip_path)
                            os.remove(csv_path)
                            
                            logger.debug(f"Data Collector: Pulled {fn}")
                    except Exception as e:
                        logger.error(f"Data Collector: Error pulling {url}: {e}")
                        
        if not dfs:
            logger.warning(f"Data Collector: No data found for {symbol} in the given range.")
            return None
            
        result = pd.concat(dfs, ignore_index=True)
        final_csv = os.path.join(self.data_dir, f"{symbol}_{interval}_{years[0]}_{years[-1]}.csv")
        result.to_csv(final_csv, index=False)
        
        logger.success(f"Data Collector: Aggregated {len(result)} candles for {symbol}. Saved to {final_csv}")
        return final_csv
