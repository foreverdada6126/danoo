import urllib.request, json
try:
    with urllib.request.urlopen("http://localhost:8000/api/chart/ohlcv?symbol=BTCUSDT&timeframe=15m") as response:
        data = json.loads(response.read())
        print(f"Candles: {len(data['candles'])}")
        print(f"Trades: {len(data.get('trades', []))}")
        if data['candles']:
            print(f"First candle time: {data['candles'][0]['time']}")
            print(f"Last candle time: {data['candles'][-1]['time']}")
        if data.get('trades'):
            print(f"First trade time: {data['trades'][0]['time']}")
            print(f"Last trade time: {data['trades'][-1]['time']}")
        
        # Check if markers are strictly within the candles time range
        # Lightweight Charts throws an error if a marker is placed OUTSIDE the loaded candlestick range sometimes.
        # It also throws an error if time values are identical but not in chronological array.
            
except Exception as e:
    print(f"Error: {e}")
